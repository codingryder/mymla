"""Test bootstrap — mocks DB + outbound HTTP before any module is imported.

Also exposes the shared in-memory `Store`, outbound `Outbox`, the `harness`
fixture, and message-builder helpers used by every flow test.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Make project root importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Required env vars so module-level reads don't blow up.
os.environ.setdefault("NEON_DSN",                   "postgresql://fake@localhost/fake")
os.environ.setdefault("META_APP_SECRET",            "")  # signature verify skipped when blank
os.environ.setdefault("META_WHATSAPP_TOKEN",        "fake-token")
os.environ.setdefault("META_PHONE_NUMBER_ID",       "000000000000000")
os.environ.setdefault("META_WEBHOOK_VERIFY_TOKEN",  "fake-verify")
os.environ.setdefault("SARVAM_API_KEY",             "fake-sarvam")
os.environ.setdefault("SENDGRID_API_KEY",           "")

# Patch psycopg2 connection so importing db.py is harmless.
_fake_cursor = MagicMock()
_fake_cursor.__enter__ = MagicMock(return_value=_fake_cursor)
_fake_cursor.__exit__  = MagicMock(return_value=False)
_fake_cursor.rowcount  = 0
_fake_cursor.fetchone  = MagicMock(return_value=None)
_fake_cursor.fetchall  = MagicMock(return_value=[])

_fake_conn = MagicMock()
_fake_conn.closed = False
_fake_conn.cursor = MagicMock(return_value=_fake_cursor)

with patch("psycopg2.connect", return_value=_fake_conn):
    import db  # noqa: F401,E402
    import cloud_api  # noqa: F401,E402


# ─── In-memory fake DB ──────────────────────────────────────────────────────

class Store:
    """Minimal in-memory stand-in for the `db` module's persistence layer."""

    def __init__(self):
        self.users: dict[str, dict] = {}
        self.complaints: list[dict] = []
        self.meetings: list[dict] = []
        self.event_invites: list[dict] = []

    # users -----------------------------------------------------------------

    def is_new_user(self, phone):
        if phone in self.users:
            return False
        self.users[phone] = {
            "phone": phone,
            "preferred_language": None,
            "aadhaar_number": None,
            "ward_id": None,
            "booth_number": None,
            "pin_code": None,
            "onboarding_complete": False,
            "current_step": None,
            "pending_flow": None,
            "session_data": {},
            "session_last_active": None,
        }
        return True

    def get_user(self, phone):
        u = self.users.get(phone)
        return dict(u) if u else None

    def set_field(self, phone, **fields):
        self.users.setdefault(phone, {"phone": phone})
        self.users[phone].update(fields)

    def reset_session(self, phone, *, hard=False):
        u = self.users.get(phone)
        if not u:
            return
        u.update({"current_step": None, "pending_flow": None, "session_data": {}})
        if hard:
            u.update({
                "preferred_language": None, "ward_id": None,
                "booth_number": None, "pin_code": None,
                "onboarding_complete": False,
            })

    def seed_onboarded_user(self, phone, *, lang="eng", ward_id=20, booth_number=80,
                            pin_code="695001"):
        """Shortcut: insert a fully-onboarded idle user for flow tests."""
        self.users[phone] = {
            "phone": phone,
            "preferred_language": lang,
            "aadhaar_number": None,
            "ward_id": ward_id,
            "booth_number": booth_number,
            "pin_code": pin_code,
            "onboarding_complete": True,
            "current_step": None,
            "pending_flow": None,
            "session_data": {},
            "session_last_active": None,
        }

    # complaints / meetings / events ----------------------------------------

    def insert_complaint(self, *, phone, ward_id, booth_number, category,
                         description_text, description_voice_url, image_media_ids,
                         local_leader_ref):
        ticket = f"MLA-GRI-WARD{ward_id:02d}-TEST5"
        self.complaints.append({
            "ticket_id": ticket, "phone": phone, "ward_id": ward_id,
            "booth_number": booth_number, "category": category,
            "description_text": description_text,
            "description_voice_url": description_voice_url,
            "image_media_ids": list(image_media_ids), "local_leader_ref": local_leader_ref,
        })
        return ticket

    def insert_meeting(self, *, phone, agenda_category, summary, preferred_window):
        meeting_id = len(self.meetings) + 1
        self.meetings.append({
            "id": meeting_id, "phone": phone,
            "agenda_category": agenda_category, "summary": summary,
            "preferred_window": preferred_window,
        })
        return meeting_id

    def insert_event_invite(self, *, phone, event_name, event_when, venue_address,
                            invite_asset_media_id):
        event_id = len(self.event_invites) + 1
        self.event_invites.append({
            "id": event_id, "phone": phone,
            "event_name": event_name, "event_when": event_when,
            "venue_address": venue_address,
            "invite_asset_media_id": invite_asset_media_id,
        })
        return event_id


# ─── Outbound capture ───────────────────────────────────────────────────────

class Outbox:
    """Captures every send_* call instead of hitting Meta Cloud API."""

    def __init__(self):
        self.sent: list[tuple[str, dict]] = []

    def text(self, to, text, preview_url=False):
        self.sent.append(("text", {"to": to, "body": text}))
        return True

    def buttons(self, to, body_text, buttons, header_text=None, footer_text=None):
        self.sent.append(("buttons", {"to": to, "body": body_text, "buttons": buttons}))
        return True

    def list_(self, to, body_text, button_text, sections, header_text=None, footer_text=None):
        self.sent.append(("list", {"to": to, "body": body_text,
                                   "button_text": button_text, "sections": sections,
                                   "header_text": header_text}))
        return True

    def last(self, kind: str | None = None) -> tuple[str, dict] | None:
        for entry in reversed(self.sent):
            if kind is None or entry[0] == kind:
                return entry
        return None

    def last_body(self, kind: str | None = None) -> str:
        entry = self.last(kind)
        if not entry:
            return ""
        return entry[1].get("body") or ""


# ─── Shared harness ─────────────────────────────────────────────────────────

@pytest.fixture
def harness():
    """Patch db.* + cloud_api.send_* with the in-memory Store/Outbox."""
    store = Store()
    outbox = Outbox()

    patches = [
        patch.object(db, "is_new_user",          side_effect=store.is_new_user),
        patch.object(db, "get_user",             side_effect=store.get_user),
        patch.object(db, "set_field",            side_effect=store.set_field),
        patch.object(db, "reset_session",        side_effect=store.reset_session),
        patch.object(db, "insert_complaint",     side_effect=store.insert_complaint),
        patch.object(db, "insert_meeting",       side_effect=store.insert_meeting),
        patch.object(db, "insert_event_invite",  side_effect=store.insert_event_invite),
        patch.object(cloud_api, "send_text",     side_effect=outbox.text),
        patch.object(cloud_api, "send_buttons",  side_effect=outbox.buttons),
        patch.object(cloud_api, "send_list",     side_effect=outbox.list_),
    ]
    for p in patches:
        p.start()
    try:
        yield store, outbox
    finally:
        for p in patches:
            p.stop()


# ─── Message-builder helpers ────────────────────────────────────────────────

def text_msg(body: str, sender: str = "919000000001") -> dict:
    return {"type": "text", "text": {"body": body}, "from": sender}


def button_reply(reply_id: str, sender: str = "919000000001") -> dict:
    return {
        "type": "interactive",
        "from": sender,
        "interactive": {"type": "button_reply", "button_reply": {"id": reply_id, "title": ""}},
    }


def list_reply(reply_id: str, sender: str = "919000000001") -> dict:
    return {
        "type": "interactive",
        "from": sender,
        "interactive": {"type": "list_reply", "list_reply": {"id": reply_id, "title": ""}},
    }
