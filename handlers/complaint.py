"""Phase 6 — Complaint Registration deep-dive flow (BRD §6).

Stages:
  1 category buttons         (complaint_category)
  2 voice OR text desc       (complaint_description)
  3 image loop (max 5)       (complaint_images)
  4 local leader ref opt     (complaint_leader_ref)
  5 final write + ticket id  (terminal — sends success card)
"""

from __future__ import annotations

import cloud_api
import db
import media as media_mod
import strings as S
import voice as voice_mod


_CATEGORY_LABEL_KEYS = {
    "cat:water":  "complaint_cat_water",
    "cat:road":   "complaint_cat_road",
    "cat:house":  "complaint_cat_house",
    "cat:waste":  "complaint_cat_waste",
    "cat:other":  "complaint_cat_other",
}


# ─── Stage 1: Category ──────────────────────────────────────────────────────

def start(phone: str, lang: str) -> None:
    db.set_field(
        phone,
        pending_flow="complaint",
        current_step="complaint_category",
        session_data={"images": []},
    )
    rows = [
        {"id": cid, "title": S.t(lang, key)[:24], "description": ""}
        for cid, key in _CATEGORY_LABEL_KEYS.items()
    ]
    cloud_api.send_list(
        to=phone,
        body_text=S.t(lang, "complaint_category_body"),
        button_text=S.t(lang, "complaint_category_button"),
        sections=[{"title": S.t(lang, "complaint_category_header")[:24], "rows": rows}],
        header_text=S.t(lang, "complaint_category_header"),
    )


def _handle_category(phone: str, lang: str, msg: dict) -> None:
    text = cloud_api.message_text(msg)
    if text not in _CATEGORY_LABEL_KEYS:
        cloud_api.send_text(phone, S.t(lang, "unknown_input"))
        start(phone, lang)
        return
    label = S.t(lang, _CATEGORY_LABEL_KEYS[text])
    session_data = {"category": label, "category_id": text, "images": []}
    db.set_field(phone, current_step="complaint_description", session_data=session_data)
    cloud_api.send_text(phone, S.t(lang, "complaint_description_prompt"))


# ─── Stage 2: Description (text or voice) ───────────────────────────────────

def _handle_description(phone: str, lang: str, user: dict, msg: dict) -> None:
    session = user.get("session_data") or {}
    kind = cloud_api.message_kind(msg)

    if kind == "audio":
        cloud_api.send_text(phone, S.t(lang, "complaint_voice_received"))
        mid = cloud_api.media_id(msg)
        if not mid:
            cloud_api.send_text(phone, S.t(lang, "complaint_voice_failed"))
            return
        audio_bytes, mime = media_mod.fetch_media(mid)
        if not audio_bytes:
            cloud_api.send_text(phone, S.t(lang, "complaint_voice_failed"))
            return
        transcript, err = voice_mod.transcribe(audio_bytes, mime or "audio/ogg", lang)
        if not transcript:
            cloud_api.send_text(phone, S.t(lang, "complaint_voice_failed"))
            return
        session["description_text"] = transcript
        session["description_voice_media_id"] = mid
        cloud_api.send_text(phone, S.t(lang, "complaint_voice_transcribed", transcript=transcript))
        db.set_field(phone, session_data=session, current_step="complaint_images")
        _ask_for_images(phone, lang, initial=True, count=0)
        return

    if kind == "text":
        text = cloud_api.message_text(msg).strip()
        if not text:
            cloud_api.send_text(phone, S.t(lang, "complaint_description_prompt"))
            return
        session["description_text"] = text
        db.set_field(phone, session_data=session, current_step="complaint_images")
        _ask_for_images(phone, lang, initial=True, count=0)
        return

    # Anything else — re-prompt.
    cloud_api.send_text(phone, S.t(lang, "complaint_description_prompt"))


# ─── Stage 3: Images (max 5 with Done button) ───────────────────────────────

MAX_IMAGES = 5


def _ask_for_images(phone: str, lang: str, *, initial: bool, count: int) -> None:
    key = "complaint_image_initial" if initial else "complaint_image_progress"
    body = S.t(lang, key, count=count)
    cloud_api.send_buttons(
        to=phone,
        body_text=body,
        buttons=[
            {"id": "complaint:done_images", "title": S.t(lang, "complaint_image_done_button")[:20]},
        ],
    )


def _handle_images(phone: str, lang: str, user: dict, msg: dict) -> None:
    session = user.get("session_data") or {}
    images: list[str] = list(session.get("images") or [])
    kind = cloud_api.message_kind(msg)
    text = cloud_api.message_text(msg)

    if text == "complaint:done_images" or kind == "interactive":
        _ask_for_leader_ref(phone, lang, session)
        return

    if kind == "image":
        if len(images) >= MAX_IMAGES:
            cloud_api.send_text(phone, S.t(lang, "complaint_image_over_cap"))
            _ask_for_leader_ref(phone, lang, session)
            return
        mid = cloud_api.media_id(msg)
        if mid:
            images.append(mid)
        session["images"] = images
        db.set_field(phone, session_data=session)
        _ask_for_images(phone, lang, initial=False, count=len(images))
        return

    # Treat any plain text as "I'm done — move on".
    if kind == "text":
        _ask_for_leader_ref(phone, lang, session)
        return


# ─── Stage 4: Local leader reference (optional) ─────────────────────────────

def _ask_for_leader_ref(phone: str, lang: str, session: dict) -> None:
    db.set_field(phone, current_step="complaint_leader_ref", session_data=session)
    cloud_api.send_buttons(
        to=phone,
        body_text=S.t(lang, "complaint_leader_ref_prompt"),
        buttons=[{"id": "complaint:skip_leader", "title": S.t(lang, "complaint_leader_skip_button")[:20]}],
    )


def _handle_leader_ref(phone: str, lang: str, user: dict, msg: dict) -> None:
    session = user.get("session_data") or {}
    text = cloud_api.message_text(msg).strip()
    if text != "complaint:skip_leader" and text:
        session["local_leader_ref"] = text
    _finalize(phone, lang, user, session)


# ─── Stage 5: Final write + ticket id ───────────────────────────────────────

def _finalize(phone: str, lang: str, user: dict, session: dict) -> None:
    ticket_id = db.insert_complaint(
        phone=phone,
        ward_id=user.get("ward_id"),
        booth_number=user.get("booth_number"),
        category=session.get("category"),
        description_text=session.get("description_text"),
        description_voice_url=session.get("description_voice_media_id"),
        image_media_ids=list(session.get("images") or []),
        local_leader_ref=session.get("local_leader_ref"),
    )
    db.set_field(phone, current_step=None, pending_flow=None, session_data={})
    cloud_api.send_text(phone, S.t(lang, "complaint_success", ticket_id=ticket_id))


# ─── Dispatcher ─────────────────────────────────────────────────────────────

def handle(phone: str, lang: str, user: dict, msg: dict) -> None:
    step = user.get("current_step")
    if step == "complaint_category":
        _handle_category(phone, lang, msg)
    elif step == "complaint_description":
        _handle_description(phone, lang, user, msg)
    elif step == "complaint_images":
        _handle_images(phone, lang, user, msg)
    elif step == "complaint_leader_ref":
        _handle_leader_ref(phone, lang, user, msg)
    else:
        start(phone, lang)
