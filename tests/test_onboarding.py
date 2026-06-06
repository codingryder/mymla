"""Onboarding state-machine smoke tests — runs the 5-step flow with mocked DB + HTTP."""

from unittest.mock import patch

import pytest


# ─── Fake DB store ──────────────────────────────────────────────────────────

class _Store:
    def __init__(self):
        self.users: dict[str, dict] = {}
        self.complaints: list[dict] = []

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
            u.update({"preferred_language": None, "ward_id": None,
                      "booth_number": None, "pin_code": None,
                      "onboarding_complete": False})

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


# ─── Outbound capture ───────────────────────────────────────────────────────

class _Outbox:
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


# ─── Fixture ────────────────────────────────────────────────────────────────

@pytest.fixture
def harness():
    import db
    import cloud_api

    store = _Store()
    outbox = _Outbox()

    patches = [
        patch.object(db, "is_new_user",        side_effect=store.is_new_user),
        patch.object(db, "get_user",           side_effect=store.get_user),
        patch.object(db, "set_field",          side_effect=store.set_field),
        patch.object(db, "reset_session",      side_effect=store.reset_session),
        patch.object(db, "insert_complaint",   side_effect=store.insert_complaint),
        patch.object(cloud_api, "send_text",   side_effect=outbox.text),
        patch.object(cloud_api, "send_buttons",side_effect=outbox.buttons),
        patch.object(cloud_api, "send_list",   side_effect=outbox.list_),
    ]
    for p in patches:
        p.start()
    try:
        yield store, outbox
    finally:
        for p in patches:
            p.stop()


def _text_msg(body: str) -> dict:
    return {"type": "text", "text": {"body": body}, "from": "919000000001"}


def _button_reply(reply_id: str) -> dict:
    return {
        "type": "interactive",
        "from": "919000000001",
        "interactive": {"type": "button_reply", "button_reply": {"id": reply_id, "title": ""}},
    }


def _list_reply(reply_id: str) -> dict:
    return {
        "type": "interactive",
        "from": "919000000001",
        "interactive": {"type": "list_reply", "list_reply": {"id": reply_id, "title": ""}},
    }


# ─── Tests ──────────────────────────────────────────────────────────────────

def test_full_onboarding_then_main_menu(harness):
    """New phone → lang Malayalam → Aadhaar skip → ward 20 → first booth → PIN → menu."""
    store, outbox = harness
    import handlers
    import handlers.onboarding as onboarding

    phone = "919000000001"

    # Step 1: language welcome
    store.is_new_user(phone)
    onboarding.start(phone)
    assert outbox.sent[-1][0] == "buttons"
    assert "lang:mal" in [b["id"] for b in outbox.sent[-1][1]["buttons"]]

    # Pick Malayalam
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _button_reply("lang:mal"))
    assert store.users[phone]["preferred_language"] == "mal"
    # Next prompt = Aadhaar with skip button
    assert outbox.sent[-1][0] == "buttons"
    assert "aadhaar:skip" in [b["id"] for b in outbox.sent[-1][1]["buttons"]]

    # Skip Aadhaar
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _button_reply("aadhaar:skip"))
    # Next prompt = ward list page 0 (wards 1–9 + "next page" row)
    assert outbox.sent[-1][0] == "list"
    page0_rows = outbox.sent[-1][1]["sections"][0]["rows"]
    assert any(r["id"] == "ward:1" for r in page0_rows)
    assert any(r["id"] == "ward_page:1" for r in page0_rows)

    # Page → 1 (wards 10–18)
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _list_reply("ward_page:1"))
    assert outbox.sent[-1][0] == "list"
    page1_rows = outbox.sent[-1][1]["sections"][0]["rows"]
    assert any(r["id"] == "ward:10" for r in page1_rows)
    assert any(r["id"] == "ward_page:2" for r in page1_rows)

    # Page → 2 (wards 19–26, no further pages)
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _list_reply("ward_page:2"))
    assert outbox.sent[-1][0] == "list"
    page2_rows = outbox.sent[-1][1]["sections"][0]["rows"]
    assert any(r["id"] == "ward:20" for r in page2_rows)

    # Pick ward 20 (Thampanoor — has 13 booths so booth list will paginate)
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _list_reply("ward:20"))
    assert store.users[phone]["ward_id"] == 20
    assert outbox.sent[-1][0] == "list"
    booth_rows = outbox.sent[-1][1]["sections"][0]["rows"]
    booth_ids = [r["id"] for r in booth_rows]
    assert "booth:80" in booth_ids
    assert "booth:skip" in booth_ids

    # Pick booth 80
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _list_reply("booth:80"))
    assert store.users[phone]["booth_number"] == 80
    # Next prompt = PIN
    assert outbox.sent[-1][0] == "text"

    # Submit bad PIN
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _text_msg("12"))
    assert store.users[phone].get("pin_code") in (None, "")
    # Submit good PIN
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _text_msg("695001"))
    assert store.users[phone]["pin_code"] == "695001"
    assert store.users[phone]["onboarding_complete"] is True
    # Main menu list should now be the most recent send.
    assert outbox.sent[-1][0] == "list"
    menu_ids = [r["id"] for r in outbox.sent[-1][1]["sections"][0]["rows"]]
    assert "menu:complaint" in menu_ids
    assert "menu:schedule" in menu_ids


def test_complaint_flow_generates_ticket(harness):
    """Onboarded user → menu → complaint → category → text desc → done → finalize → ticket id."""
    store, outbox = harness
    import handlers

    phone = "919000000002"
    store.users[phone] = {
        "phone": phone,
        "preferred_language": "eng",
        "aadhaar_number": None,
        "ward_id": 20,
        "booth_number": 80,
        "pin_code": "695001",
        "onboarding_complete": True,
        "current_step": None,
        "pending_flow": None,
        "session_data": {},
        "session_last_active": None,
    }

    # Pick complaint from menu
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _list_reply("menu:complaint"))
    assert store.users[phone]["current_step"] == "complaint_category"

    # Pick Drinking Water category
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _list_reply("cat:water"))
    assert store.users[phone]["current_step"] == "complaint_description"

    # Send text description
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _text_msg("Pipe burst on Pulayanarkotta road since yesterday."))
    assert store.users[phone]["current_step"] == "complaint_images"
    assert store.users[phone]["session_data"]["description_text"].startswith("Pipe burst")

    # Click "Done Uploading" (no images attached)
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _button_reply("complaint:done_images"))
    assert store.users[phone]["current_step"] == "complaint_leader_ref"

    # Skip local leader ref
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _button_reply("complaint:skip_leader"))

    # Should now be finalized — ticket inserted, success card sent.
    assert len(store.complaints) == 1
    ticket = store.complaints[0]["ticket_id"]
    assert ticket.startswith("MLA-GRI-WARD20-")
    # Success message should include the ticket id verbatim.
    success_text = next(
        (msg[1]["body"] for msg in reversed(outbox.sent) if msg[0] == "text"), ""
    )
    assert ticket in success_text
    assert store.users[phone]["current_step"] is None
    assert store.users[phone]["pending_flow"] is None
