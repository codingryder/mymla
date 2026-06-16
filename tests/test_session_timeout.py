"""30-minute session timeout (BRD §2).

Two layers:
  - unit: `session.is_expired` / `session.reset_if_expired` behave correctly
    against the inactivity threshold (profile preserved on soft reset).
  - integration: `bot._handle_message` for a timed-out onboarded user sends the
    reset notice and re-renders the main menu without losing their language/ward/PIN.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.conftest import text_msg


def _stale(minutes_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)


def test_is_expired_returns_false_when_session_is_fresh(harness):
    import session as session_mod

    user = {"phone": "919000000050", "session_last_active": _stale(5)}
    assert session_mod.is_expired(user) is False


def test_is_expired_returns_true_past_threshold(harness):
    import session as session_mod

    user = {"phone": "919000000051", "session_last_active": _stale(45)}
    assert session_mod.is_expired(user) is True


def test_is_expired_returns_false_when_last_active_is_none(harness):
    """Users without a `session_last_active` timestamp have never been active — not expired."""
    import session as session_mod

    user = {"phone": "919000000052", "session_last_active": None}
    assert session_mod.is_expired(user) is False


def test_reset_if_expired_does_soft_reset_and_preserves_profile(harness):
    """Soft reset wipes step/flow/session_data but keeps lang/ward/booth/PIN intact."""
    store, _outbox = harness
    import session as session_mod

    phone = "919000000053"
    store.seed_onboarded_user(phone, lang="mal", ward_id=20, booth_number=80, pin_code="695001")
    # Put them mid-complaint-flow with stale activity.
    store.set_field(
        phone,
        current_step="complaint_description",
        pending_flow="complaint",
        session_data={"category": "water"},
        session_last_active=_stale(40),
    )

    user = store.get_user(phone)
    assert session_mod.reset_if_expired(user) is True

    after = store.get_user(phone)
    # Step/flow/session cleared.
    assert after["current_step"] is None
    assert after["pending_flow"] is None
    assert after["session_data"] == {}
    # Profile preserved.
    assert after["preferred_language"] == "mal"
    assert after["ward_id"] == 20
    assert after["booth_number"] == 80
    assert after["pin_code"] == "695001"
    assert after["onboarding_complete"] is True


def test_handle_message_for_timed_out_onboarded_user(harness):
    """End-to-end: bot._handle_message → expired user gets the reset notice + main menu."""
    store, outbox = harness
    import bot

    phone = "919000000054"
    store.seed_onboarded_user(phone, lang="eng")
    store.set_field(
        phone,
        current_step="meeting_summary",
        pending_flow="meeting",
        session_data={"agenda_id": "agenda:dev"},
        session_last_active=_stale(60),
    )

    bot._handle_message(text_msg("hello?", sender=phone))

    # Find the reset notice (plain text) and the main menu list.
    kinds = [entry[0] for entry in outbox.sent]
    assert "text" in kinds, "Expected the session_reset_notice text to be sent"
    assert "list" in kinds, "Expected the main menu list to be re-rendered"

    # Menu list should contain the five service options.
    menu_entry = next(e for e in reversed(outbox.sent) if e[0] == "list")
    menu_ids = [r["id"] for r in menu_entry[1]["sections"][0]["rows"]]
    assert {"menu:complaint", "menu:meeting", "menu:location",
            "menu:event", "menu:schedule"} <= set(menu_ids)

    # Profile preserved, session cleared.
    after = store.get_user(phone)
    assert after["preferred_language"] == "eng"
    assert after["current_step"] is None
    assert after["pending_flow"] is None
