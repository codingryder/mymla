"""Onboarding state-machine smoke tests — runs the 5-step flow with mocked DB + HTTP.

Uses the shared `harness` fixture from conftest.py.
"""

from tests.conftest import text_msg, button_reply, list_reply


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
    handlers.dispatch(phone, user, button_reply("lang:mal"))
    assert store.users[phone]["preferred_language"] == "mal"
    # Next prompt = Aadhaar with skip button
    assert outbox.sent[-1][0] == "buttons"
    assert "aadhaar:skip" in [b["id"] for b in outbox.sent[-1][1]["buttons"]]

    # Skip Aadhaar
    user = store.get_user(phone)
    handlers.dispatch(phone, user, button_reply("aadhaar:skip"))
    # Next prompt = ward list page 0 (wards 1–9 + "next page" row)
    assert outbox.sent[-1][0] == "list"
    page0_rows = outbox.sent[-1][1]["sections"][0]["rows"]
    assert any(r["id"] == "ward:1" for r in page0_rows)
    assert any(r["id"] == "ward_page:1" for r in page0_rows)

    # Page → 1 (wards 10–18)
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("ward_page:1"))
    assert outbox.sent[-1][0] == "list"
    page1_rows = outbox.sent[-1][1]["sections"][0]["rows"]
    assert any(r["id"] == "ward:10" for r in page1_rows)
    assert any(r["id"] == "ward_page:2" for r in page1_rows)

    # Page → 2 (wards 19–26, no further pages)
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("ward_page:2"))
    assert outbox.sent[-1][0] == "list"
    page2_rows = outbox.sent[-1][1]["sections"][0]["rows"]
    assert any(r["id"] == "ward:20" for r in page2_rows)

    # Pick ward 20 (Thampanoor — has 13 booths so booth list will paginate)
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("ward:20"))
    assert store.users[phone]["ward_id"] == 20
    assert outbox.sent[-1][0] == "list"
    booth_rows = outbox.sent[-1][1]["sections"][0]["rows"]
    booth_ids = [r["id"] for r in booth_rows]
    assert "booth:80" in booth_ids
    assert "booth:skip" in booth_ids

    # Pick booth 80
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("booth:80"))
    assert store.users[phone]["booth_number"] == 80
    # Next prompt = PIN
    assert outbox.sent[-1][0] == "text"

    # Submit bad PIN
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("12"))
    assert store.users[phone].get("pin_code") in (None, "")
    # Submit good PIN
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("695001"))
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
    store.seed_onboarded_user(phone, lang="eng", ward_id=20, booth_number=80)

    # Pick complaint from menu
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("menu:complaint"))
    assert store.users[phone]["current_step"] == "complaint_category"

    # Pick Drinking Water category
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("cat:water"))
    assert store.users[phone]["current_step"] == "complaint_description"

    # Send text description
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("Pipe burst on Pulayanarkotta road since yesterday."))
    assert store.users[phone]["current_step"] == "complaint_images"
    assert store.users[phone]["session_data"]["description_text"].startswith("Pipe burst")

    # Click "Done Uploading" (no images attached)
    user = store.get_user(phone)
    handlers.dispatch(phone, user, button_reply("complaint:done_images"))
    assert store.users[phone]["current_step"] == "complaint_leader_ref"

    # Skip local leader ref
    user = store.get_user(phone)
    handlers.dispatch(phone, user, button_reply("complaint:skip_leader"))

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
