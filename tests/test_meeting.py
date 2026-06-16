"""Meeting flow state-machine test (BRD §7.1).

Menu → meeting → agenda pick → summary text → preferred window text →
insert_meeting fired, session cleared, success message sent.
"""

from tests.conftest import text_msg, list_reply


def test_meeting_flow_books_appointment(harness):
    store, outbox = harness
    import handlers

    phone = "919000000010"
    store.seed_onboarded_user(phone, lang="eng", ward_id=14, booth_number=4)

    # Pick "Schedule a Meeting" from the main menu
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("menu:meeting"))
    assert store.users[phone]["pending_flow"] == "meeting"
    assert store.users[phone]["current_step"] == "meeting_agenda"
    # Agenda prompt is a list with the three BRD-mandated categories.
    assert outbox.sent[-1][0] == "list"
    agenda_ids = [r["id"] for r in outbox.sent[-1][1]["sections"][0]["rows"]]
    assert {"agenda:dev", "agenda:welfare", "agenda:grievance"} <= set(agenda_ids)

    # Pick "Welfare Support"
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("agenda:welfare"))
    assert store.users[phone]["current_step"] == "meeting_summary"
    assert store.users[phone]["session_data"]["agenda_id"] == "agenda:welfare"
    assert "Welfare Support" in store.users[phone]["session_data"]["agenda"]
    # Summary prompt is a plain text question.
    assert outbox.sent[-1][0] == "text"

    # Whitespace-only summary should be re-prompted, not accepted.
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("   "))
    assert store.users[phone]["current_step"] == "meeting_summary"

    # Real summary advances to window step.
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("Need help with pension paperwork for elderly father."))
    assert store.users[phone]["current_step"] == "meeting_window"
    assert store.users[phone]["session_data"]["summary"].startswith("Need help")
    assert outbox.sent[-1][0] == "text"

    # Preferred window finalizes the booking.
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("Next week, weekday afternoons preferred"))

    # Meeting row persisted with all 3 captured fields.
    assert len(store.meetings) == 1
    booking = store.meetings[0]
    assert booking["phone"] == phone
    assert "Welfare Support" in booking["agenda_category"]
    assert booking["summary"].startswith("Need help")
    assert "weekday afternoons" in booking["preferred_window"]

    # Session cleared back to idle.
    assert store.users[phone]["current_step"] is None
    assert store.users[phone]["pending_flow"] is None
    assert store.users[phone]["session_data"] == {}

    # Success message sent last.
    assert outbox.sent[-1][0] == "text"
    assert outbox.last_body("text")  # non-empty


def test_meeting_rejects_unknown_agenda(harness):
    """Typing a free-text agenda instead of picking should re-prompt and stay on the same step."""
    store, outbox = harness
    import handlers

    phone = "919000000011"
    store.seed_onboarded_user(phone, lang="eng")

    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("menu:meeting"))
    assert store.users[phone]["current_step"] == "meeting_agenda"

    # Bogus agenda id — should fall through to "unknown_input" + re-render the list.
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("agenda:bogus"))
    assert store.users[phone]["current_step"] == "meeting_agenda"
    # Last send is the re-rendered agenda list.
    assert outbox.sent[-1][0] == "list"
