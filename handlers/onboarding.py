"""Phase 1 — 5-step onboarding (BRD §3).

Step sequence:
  await_lang     →  await_aadhaar  →  await_ward  →  await_booth  →  await_pin
  (mandatory)        (optional)        (mandatory)   (optional)      (mandatory)

On PIN success we flip onboarding_complete=TRUE and forward into the main menu.
"""

from __future__ import annotations

import re

import cloud_api
import db
import strings as S
import wards as W

from . import menu


# ─── Step 1: Language ───────────────────────────────────────────────────────

def start(phone: str, lang: str | None = None) -> None:
    """Send the bilingual welcome. lang param ignored — we render in both."""
    db.set_field(phone, current_step="await_lang", preferred_language=None)
    cloud_api.send_buttons(
        to=phone,
        body_text=S.t("mal", "welcome_body"),
        buttons=[
            {"id": "lang:mal", "title": "മലയാളം"},
            {"id": "lang:eng", "title": "English"},
        ],
    )


def _handle_lang(phone: str, msg: dict) -> None:
    text = cloud_api.message_text(msg)
    if text == "lang:mal":
        chosen = "mal"
    elif text == "lang:eng":
        chosen = "eng"
    else:
        # Unknown — re-prompt.
        cloud_api.send_text(phone, S.t("mal", "unknown_input"))
        start(phone)
        return
    db.set_field(phone, preferred_language=chosen)
    _ask_aadhaar(phone, chosen)


# ─── Step 2: Aadhaar (optional) ─────────────────────────────────────────────

def _ask_aadhaar(phone: str, lang: str) -> None:
    db.set_field(phone, current_step="await_aadhaar")
    cloud_api.send_buttons(
        to=phone,
        body_text=S.t(lang, "aadhaar_prompt"),
        buttons=[{"id": "aadhaar:skip", "title": S.t(lang, "aadhaar_skip_button")[:20]}],
    )


def _handle_aadhaar(phone: str, lang: str, msg: dict) -> None:
    text = cloud_api.message_text(msg).strip()
    if text == "aadhaar:skip":
        _ask_ward(phone, lang)
        return
    digits = re.sub(r"\D", "", text)
    if len(digits) != 12:
        cloud_api.send_text(phone, S.t(lang, "aadhaar_validation_error"))
        _ask_aadhaar(phone, lang)
        return
    db.set_field(phone, aadhaar_number=digits)
    cloud_api.send_text(phone, S.t(lang, "aadhaar_saved"))
    _ask_ward(phone, lang)


# ─── Step 3: Ward (mandatory list) ──────────────────────────────────────────

def _ward_section_rows(lang: str, page: int) -> tuple[list[dict], bool]:
    """Slice 26 wards into pages of 9 (WhatsApp List = 10 rows max)."""
    per_page = 9
    start_i = page * per_page
    end_i = start_i + per_page
    sliced = list(W.all_wards())[start_i:end_i]
    has_next = end_i < 26
    rows: list[dict] = []
    for w in sliced:
        rows.append({
            "id": f"ward:{w['id']}",
            "title": (w["name_mal"] if lang == "mal" else w["name_eng"])[:24],
            "description": (
                f"Ward {w['id']}" if lang == "eng"
                else f"വാർഡ് {w['id']}"
            )[:72],
        })
    return rows, has_next


def _ask_ward(phone: str, lang: str, page: int = 0) -> None:
    db.set_field(phone, current_step="await_ward", session_data={"ward_page": page})
    rows, has_next = _ward_section_rows(lang, page)
    if has_next:
        rows.append({
            "id": f"ward_page:{page + 1}",
            "title": S.t(lang, "booth_next_page")[:24],
            "description": "",
        })
    cloud_api.send_list(
        to=phone,
        body_text=S.t(lang, "ward_prompt"),
        button_text=S.t(lang, "ward_list_button"),
        sections=[{"title": S.t(lang, "ward_section_title")[:24], "rows": rows}],
        header_text=S.t(lang, "ward_list_header"),
    )


def _handle_ward(phone: str, lang: str, msg: dict) -> None:
    text = cloud_api.message_text(msg)
    m_page = re.match(r"^ward_page:(\d+)$", text)
    if m_page:
        _ask_ward(phone, lang, page=int(m_page.group(1)))
        return
    m = re.match(r"^ward:(\d+)$", text)
    if not m:
        cloud_api.send_text(phone, S.t(lang, "unknown_input"))
        _ask_ward(phone, lang)
        return
    ward_id = int(m.group(1))
    if not W.ward_by_id(ward_id):
        cloud_api.send_text(phone, S.t(lang, "unknown_input"))
        _ask_ward(phone, lang)
        return
    db.set_field(phone, ward_id=ward_id)
    _ask_booth(phone, lang, ward_id, page=0)


# ─── Step 4: Booth (optional, ward-scoped) ──────────────────────────────────

def _ask_booth(phone: str, lang: str, ward_id: int, page: int = 0) -> None:
    booths, has_next = W.paginate_booths(ward_id, page=page)
    if not booths:
        # Ward has no booths recorded — skip straight to PIN.
        _ask_pin(phone, lang)
        return
    ward_name = W.ward_name(ward_id, lang)
    db.set_field(
        phone,
        current_step="await_booth",
        session_data={"booth_page": page},
    )
    rows = [
        {
            "id": f"booth:{b}",
            "title": S.t(lang, "booth_row_title", booth=b)[:24],
            "description": "",
        }
        for b in booths
    ]
    if has_next:
        rows.append({
            "id": f"booth_page:{page + 1}",
            "title": S.t(lang, "booth_next_page")[:24],
            "description": "",
        })
    rows.append({
        "id": "booth:skip",
        "title": S.t(lang, "booth_skip_button")[:24],
        "description": "",
    })
    cloud_api.send_list(
        to=phone,
        body_text=S.t(lang, "booth_prompt", ward_name=ward_name),
        button_text=S.t(lang, "booth_list_button"),
        sections=[{"title": S.t(lang, "booth_section_title")[:24], "rows": rows}],
        header_text=S.t(lang, "booth_list_header"),
    )


def _handle_booth(phone: str, lang: str, user: dict, msg: dict) -> None:
    text = cloud_api.message_text(msg)
    ward_id = user.get("ward_id") or 0

    if text == "booth:skip":
        _ask_pin(phone, lang)
        return

    m_page = re.match(r"^booth_page:(\d+)$", text)
    if m_page:
        _ask_booth(phone, lang, ward_id, page=int(m_page.group(1)))
        return

    m = re.match(r"^booth:(\d+)$", text)
    if not m:
        cloud_api.send_text(phone, S.t(lang, "unknown_input"))
        _ask_booth(phone, lang, ward_id, page=user.get("session_data", {}).get("booth_page", 0))
        return
    booth = int(m.group(1))
    if booth not in W.booths_for_ward(ward_id):
        cloud_api.send_text(phone, S.t(lang, "unknown_input"))
        _ask_booth(phone, lang, ward_id, page=user.get("session_data", {}).get("booth_page", 0))
        return
    db.set_field(phone, booth_number=booth)
    _ask_pin(phone, lang)


# ─── Step 5: PIN (mandatory) ────────────────────────────────────────────────

def _ask_pin(phone: str, lang: str) -> None:
    db.set_field(phone, current_step="await_pin")
    cloud_api.send_text(phone, S.t(lang, "pin_prompt"))


def _handle_pin(phone: str, lang: str, msg: dict) -> None:
    text = cloud_api.message_text(msg).strip()
    digits = re.sub(r"\D", "", text)
    if len(digits) != 6:
        cloud_api.send_text(phone, S.t(lang, "pin_validation_error"))
        return
    db.set_field(
        phone,
        pin_code=digits,
        onboarding_complete=True,
        current_step=None,
        session_data={},
    )
    cloud_api.send_text(phone, S.t(lang, "onboarding_complete"))
    menu.start(phone, lang)


# ─── Dispatcher ─────────────────────────────────────────────────────────────

def handle(phone: str, lang: str, user: dict, msg: dict) -> None:
    step = user.get("current_step")
    if step == "await_lang":
        _handle_lang(phone, msg)
    elif step == "await_aadhaar":
        _handle_aadhaar(phone, lang, msg)
    elif step == "await_ward":
        _handle_ward(phone, lang, msg)
    elif step == "await_booth":
        _handle_booth(phone, lang, user, msg)
    elif step == "await_pin":
        _handle_pin(phone, lang, msg)
    else:
        resume(phone, user)


def resume(phone: str, user: dict) -> None:
    """Resume onboarding at the earliest missing field."""
    lang = user.get("preferred_language")
    if not lang:
        start(phone)
        return
    if not user.get("aadhaar_number") and user.get("current_step") in (None, ""):
        # Aadhaar is optional — only re-ask if we haven't seen a deliberate skip
        # signal recorded by `_handle_aadhaar`. In practice this branch is rare;
        # we just fall through to ward.
        pass
    if not user.get("ward_id"):
        _ask_ward(phone, lang)
        return
    if not user.get("pin_code"):
        _ask_pin(phone, lang)
        return
    # Everything filled — finalize.
    db.set_field(phone, onboarding_complete=True, current_step=None)
    menu.start(phone, lang)
