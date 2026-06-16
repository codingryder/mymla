"""7-day program chart rendering (BRD §7.4).

Stubs `db.get_mla_schedule_next_7_days` to exercise the empty + populated branches.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from tests.conftest import list_reply


def test_schedule_empty_shows_no_events_message(harness):
    store, outbox = harness
    import db
    import handlers

    phone = "919000000040"
    store.seed_onboarded_user(phone, lang="eng")

    with patch.object(db, "get_mla_schedule_next_7_days", return_value=[]):
        user = store.get_user(phone)
        handlers.dispatch(phone, user, list_reply("menu:schedule"))

    body = outbox.last_body("text")
    assert "Upcoming 7 Days" in body                          # header
    assert "No public programs" in body                        # empty-state copy
    assert outbox.sent[-1][0] == "list"                        # menu auto-rendered


def test_schedule_populated_renders_each_row(harness):
    store, outbox = harness
    import db
    import handlers

    phone = "919000000041"
    store.seed_onboarded_user(phone, lang="eng")

    fake_rows = [
        {"event_date": date(2026, 6, 18), "title": "Town Hall on Drainage",
         "venue": "Chakai Community Centre"},
        {"event_date": date(2026, 6, 20), "title": "Ward 14 Site Visit",
         "venue": "Vettukaud Junction"},
    ]
    with patch.object(db, "get_mla_schedule_next_7_days", return_value=fake_rows):
        user = store.get_user(phone)
        handlers.dispatch(phone, user, list_reply("menu:schedule"))

    body = outbox.last_body("text")
    assert "Town Hall on Drainage" in body
    assert "Chakai Community Centre" in body
    assert "Ward 14 Site Visit" in body
    assert "Vettukaud Junction" in body
    # Dates rendered in the "Thu 18 Jun" short form.
    assert "18 Jun" in body
    assert "20 Jun" in body
    assert outbox.sent[-1][0] == "list"                        # menu auto-rendered
