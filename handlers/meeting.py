"""Phase 7.1 — Schedule a Meeting (BRD §7.1).

Workflow: agenda category → summary text → preferred window → confirmation.
"""

from __future__ import annotations

import cloud_api
import db
import strings as S


_AGENDA_LABELS = {
    "agenda:dev":       "meeting_agenda_dev",
    "agenda:welfare":   "meeting_agenda_welfare",
    "agenda:grievance": "meeting_agenda_grievance",
}


def start(phone: str, lang: str) -> None:
    db.set_field(
        phone,
        pending_flow="meeting",
        current_step="meeting_agenda",
        session_data={},
    )
    rows = [
        {"id": cid, "title": S.t(lang, key)[:24], "description": ""}
        for cid, key in _AGENDA_LABELS.items()
    ]
    cloud_api.send_list(
        to=phone,
        body_text=S.t(lang, "meeting_agenda_body"),
        button_text=S.t(lang, "meeting_agenda_button"),
        sections=[{"title": S.t(lang, "meeting_agenda_header")[:24], "rows": rows}],
        header_text=S.t(lang, "meeting_agenda_header"),
    )


def _handle_agenda(phone: str, lang: str, msg: dict) -> None:
    text = cloud_api.message_text(msg)
    if text not in _AGENDA_LABELS:
        cloud_api.send_text(phone, S.t(lang, "unknown_input"))
        start(phone, lang)
        return
    label = S.t(lang, _AGENDA_LABELS[text])
    db.set_field(
        phone,
        current_step="meeting_summary",
        session_data={"agenda": label, "agenda_id": text},
    )
    cloud_api.send_text(phone, S.t(lang, "meeting_summary_prompt"))


def _handle_summary(phone: str, lang: str, user: dict, msg: dict) -> None:
    text = cloud_api.message_text(msg).strip()
    if not text:
        cloud_api.send_text(phone, S.t(lang, "meeting_summary_prompt"))
        return
    session = user.get("session_data") or {}
    session["summary"] = text
    db.set_field(phone, current_step="meeting_window", session_data=session)
    cloud_api.send_text(phone, S.t(lang, "meeting_window_prompt"))


def _handle_window(phone: str, lang: str, user: dict, msg: dict) -> None:
    text = cloud_api.message_text(msg).strip()
    if not text:
        cloud_api.send_text(phone, S.t(lang, "meeting_window_prompt"))
        return
    session = user.get("session_data") or {}
    db.insert_meeting(
        phone=phone,
        agenda_category=session.get("agenda") or "",
        summary=session.get("summary") or "",
        preferred_window=text,
    )
    db.set_field(phone, current_step=None, pending_flow=None, session_data={})
    cloud_api.send_text(phone, S.t(lang, "meeting_success"))


def handle(phone: str, lang: str, user: dict, msg: dict) -> None:
    step = user.get("current_step")
    if step == "meeting_agenda":
        _handle_agenda(phone, lang, msg)
    elif step == "meeting_summary":
        _handle_summary(phone, lang, user, msg)
    elif step == "meeting_window":
        _handle_window(phone, lang, user, msg)
    else:
        start(phone, lang)
