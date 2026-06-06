"""Phase 7.3 — Invite for an Event (BRD §7.3).

Sequence: name/objective → datetime → venue → upload invitation asset (PNG/PDF) →
persist row + success ack.
"""

from __future__ import annotations

import cloud_api
import db
import strings as S


def start(phone: str, lang: str) -> None:
    db.set_field(
        phone,
        pending_flow="event",
        current_step="event_name",
        session_data={},
    )
    cloud_api.send_text(phone, S.t(lang, "event_name_prompt"))


def _handle_name(phone: str, lang: str, user: dict, msg: dict) -> None:
    text = cloud_api.message_text(msg).strip()
    if not text:
        cloud_api.send_text(phone, S.t(lang, "event_name_prompt"))
        return
    session = user.get("session_data") or {}
    session["name"] = text
    db.set_field(phone, current_step="event_when", session_data=session)
    cloud_api.send_text(phone, S.t(lang, "event_datetime_prompt"))


def _handle_when(phone: str, lang: str, user: dict, msg: dict) -> None:
    text = cloud_api.message_text(msg).strip()
    if not text:
        cloud_api.send_text(phone, S.t(lang, "event_datetime_prompt"))
        return
    session = user.get("session_data") or {}
    session["when"] = text
    db.set_field(phone, current_step="event_venue", session_data=session)
    cloud_api.send_text(phone, S.t(lang, "event_venue_prompt"))


def _handle_venue(phone: str, lang: str, user: dict, msg: dict) -> None:
    text = cloud_api.message_text(msg).strip()
    if not text:
        cloud_api.send_text(phone, S.t(lang, "event_venue_prompt"))
        return
    session = user.get("session_data") or {}
    session["venue"] = text
    db.set_field(phone, current_step="event_asset", session_data=session)
    cloud_api.send_buttons(
        to=phone,
        body_text=S.t(lang, "event_asset_prompt"),
        buttons=[{"id": "event:skip_asset", "title": S.t(lang, "event_asset_skip_button")[:20]}],
    )


def _handle_asset(phone: str, lang: str, user: dict, msg: dict) -> None:
    session = user.get("session_data") or {}
    kind = cloud_api.message_kind(msg)
    text = cloud_api.message_text(msg)
    asset_id: str | None = None

    if text == "event:skip_asset":
        asset_id = None
    elif kind in ("image", "document"):
        asset_id = cloud_api.media_id(msg)
    elif kind == "text":
        # If user typed instead of attaching, treat as skip.
        asset_id = None
    else:
        cloud_api.send_text(phone, S.t(lang, "event_asset_prompt"))
        return

    db.insert_event_invite(
        phone=phone,
        event_name=session.get("name") or "",
        event_when=session.get("when") or "",
        venue_address=session.get("venue") or "",
        invite_asset_media_id=asset_id,
    )
    db.set_field(phone, current_step=None, pending_flow=None, session_data={})
    cloud_api.send_text(phone, S.t(lang, "event_success"))


def handle(phone: str, lang: str, user: dict, msg: dict) -> None:
    step = user.get("current_step")
    if step == "event_name":
        _handle_name(phone, lang, user, msg)
    elif step == "event_when":
        _handle_when(phone, lang, user, msg)
    elif step == "event_venue":
        _handle_venue(phone, lang, user, msg)
    elif step == "event_asset":
        _handle_asset(phone, lang, user, msg)
    else:
        start(phone, lang)
