"""Where-is-my-MLA status card rendering (BRD §7.2).

Stubs `db.get_mla_location` to drive each of the three status keys and verifies
the rendered card includes the right status sentence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import list_reply


def _mla_row(status_key: str, ward_id: int | None = None) -> dict:
    return {
        "status_key": status_key,
        "status_ward_id": ward_id,
        "updated_at": datetime(2026, 6, 16, 9, 30, tzinfo=timezone.utc),
    }


def test_location_office_status(harness):
    store, outbox = harness
    import db
    import handlers

    phone = "919000000030"
    store.seed_onboarded_user(phone, lang="eng")

    with patch.object(db, "get_mla_location", return_value=_mla_row("office")):
        user = store.get_user(phone)
        handlers.dispatch(phone, user, list_reply("menu:location"))

    last = outbox.last("text")
    assert last is not None
    body = last[1]["body"]
    assert "constituency office" in body  # English "office" status string
    assert "16 Jun 2026" in body            # updated_at formatted in the card


def test_location_assembly_status(harness):
    store, outbox = harness
    import db
    import handlers

    phone = "919000000031"
    store.seed_onboarded_user(phone, lang="eng")

    with patch.object(db, "get_mla_location", return_value=_mla_row("assembly")):
        user = store.get_user(phone)
        handlers.dispatch(phone, user, list_reply("menu:location"))

    body = outbox.last_body("text")
    assert "Legislative Assembly" in body


def test_location_inspection_status_includes_ward_name(harness):
    """When status is 'inspection', the ward name must be interpolated into the card."""
    store, outbox = harness
    import db
    import handlers

    phone = "919000000032"
    store.seed_onboarded_user(phone, lang="eng")

    with patch.object(db, "get_mla_location", return_value=_mla_row("inspection", ward_id=12)):
        user = store.get_user(phone)
        handlers.dispatch(phone, user, list_reply("menu:location"))

    body = outbox.last_body("text")
    assert "inspection" in body.lower()
    assert "Valiyathura" in body  # Ward 12 per wards.py
