"""Phase 2 — Main Menu Service Navigation Dashboard (BRD §5).

Five routes: Complaint, Meeting, Where-is-my-MLA, Event, Schedule.
"""

from __future__ import annotations

import cloud_api
import db
import strings as S

from . import complaint, event, location, meeting, schedule


_MENU_ROUTES = {
    "menu:complaint": "complaint",
    "menu:meeting":   "meeting",
    "menu:location":  "location",
    "menu:event":     "event",
    "menu:schedule":  "schedule",
}


def start(phone: str, lang: str) -> None:
    db.set_field(phone, current_step=None, pending_flow=None, session_data={})
    rows = [
        {"id": "menu:complaint", "title": S.t(lang, "menu_opt_complaint")[:24], "description": ""},
        {"id": "menu:meeting",   "title": S.t(lang, "menu_opt_meeting")[:24],   "description": ""},
        {"id": "menu:location",  "title": S.t(lang, "menu_opt_location")[:24],  "description": ""},
        {"id": "menu:event",     "title": S.t(lang, "menu_opt_event")[:24],     "description": ""},
        {"id": "menu:schedule",  "title": S.t(lang, "menu_opt_schedule")[:24],  "description": ""},
    ]
    cloud_api.send_list(
        to=phone,
        body_text=S.t(lang, "menu_body"),
        button_text=S.t(lang, "menu_button"),
        sections=[{"title": S.t(lang, "menu_section_title")[:24], "rows": rows}],
        header_text=S.t(lang, "menu_header"),
    )


def handle_menu_selection(phone: str, lang: str, selection_id: str) -> None:
    route = _MENU_ROUTES.get(selection_id)
    if route == "complaint":
        complaint.start(phone, lang)
    elif route == "meeting":
        meeting.start(phone, lang)
    elif route == "location":
        location.send(phone, lang)
    elif route == "event":
        event.start(phone, lang)
    elif route == "schedule":
        schedule.send(phone, lang)
    else:
        cloud_api.send_text(phone, S.t(lang, "unknown_input"))
        start(phone, lang)
