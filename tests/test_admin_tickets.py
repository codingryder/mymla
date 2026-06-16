"""Phase 3.1 — admin ticket viewer (HTTP Basic Auth, fail-closed)."""

from __future__ import annotations

import os
from base64 import b64encode
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "office")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    import bot
    return TestClient(bot.app)


@pytest.fixture
def client_unconfigured(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "")
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    import bot
    return TestClient(bot.app)


def _auth(user: str, pw: str) -> dict[str, str]:
    token = b64encode(f"{user}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def fake_complaints():
    """A small list of complaint rows the mocked DB cursor returns."""
    return [
        {
            "ticket_id": "MLA-GRI-WARD20-A1B2C", "phone": "919000000001",
            "ward_id": 20, "booth_number": 80, "category": "Drinking Water",
            "description_text": "Pipe burst on main road since yesterday.",
            "description_voice_url": None, "image_media_ids": ["m1", "m2"],
            "local_leader_ref": None,
            "created_at": datetime(2026, 6, 17, 9, 30, tzinfo=timezone.utc),
            "status": "OPEN",
        },
        {
            "ticket_id": "MLA-GRI-WARD14-Z9Y8X", "phone": "919000000002",
            "ward_id": 14, "booth_number": 4, "category": "Road",
            "description_text": "Pothole near junction.",
            "description_voice_url": "media-99", "image_media_ids": [],
            "local_leader_ref": "Ward Member Anil",
            "created_at": datetime(2026, 6, 16, 14, 15, tzinfo=timezone.utc),
            "status": "IN_PROGRESS",
        },
    ]


@pytest.fixture
def mock_db(fake_complaints):
    """Patch db.get_connection so admin queries don't hit a real Neon."""
    import db

    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    # First execute() is fetch_tickets — returns rows. Second is counts — returns aggregates.
    cursor.fetchall.side_effect = [
        list(fake_complaints),                          # fetch_tickets
        [("OPEN", 5), ("IN_PROGRESS", 2), ("RESOLVED", 9)],  # fetch_counts_by_status
    ]
    conn = MagicMock()
    conn.cursor = MagicMock(return_value=cursor)

    with patch.object(db, "get_connection", return_value=conn):
        yield conn, cursor


# ─── Auth ───────────────────────────────────────────────────────────────────

def test_admin_returns_401_without_auth(client):
    r = client.get("/admin/tickets")
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == "Basic"


def test_admin_returns_401_with_wrong_credentials(client):
    r = client.get("/admin/tickets", headers=_auth("office", "WRONG"))
    assert r.status_code == 401


def test_admin_returns_503_when_env_not_configured(client_unconfigured):
    r = client_unconfigured.get("/admin/tickets", headers=_auth("anything", "anything"))
    assert r.status_code == 503


def test_admin_home_authenticates_and_renders(client, mock_db):
    # admin_home doesn't hit the DB but auth still applies.
    r = client.get("/admin/", headers=_auth("office", "secret"))
    assert r.status_code == 200
    assert "MLA Office Console" in r.text
    assert "Citizen complaints" in r.text


# ─── Ticket viewer ──────────────────────────────────────────────────────────

def test_admin_tickets_renders_rows(client, mock_db, fake_complaints):
    r = client.get("/admin/tickets", headers=_auth("office", "secret"))
    assert r.status_code == 200
    body = r.text
    # Each ticket id appears verbatim.
    for row in fake_complaints:
        assert row["ticket_id"] in body
    # Status badges rendered.
    assert "status-OPEN" in body
    assert "status-IN_PROGRESS" in body
    # Counts from the second cursor.fetchall() landed in the filter bar.
    assert "(5)" in body   # OPEN count
    assert "(16)" in body  # ALL = 5 + 2 + 9
    # Image and voice indicators (emoji-based).
    assert "📷" in body
    assert "🎙" in body


def test_admin_tickets_status_filter_applied_to_sql(client, mock_db):
    _conn, cursor = mock_db
    r = client.get("/admin/tickets?status=RESOLVED", headers=_auth("office", "secret"))
    assert r.status_code == 200
    sql = cursor.execute.call_args_list[0].args[0]
    args = cursor.execute.call_args_list[0].args[1]
    assert "status = %s" in sql
    assert "RESOLVED" in args


def test_admin_tickets_status_all_means_no_status_filter(client, mock_db):
    _conn, cursor = mock_db
    r = client.get("/admin/tickets?status=ALL", headers=_auth("office", "secret"))
    assert r.status_code == 200
    sql = cursor.execute.call_args_list[0].args[0]
    assert "status = %s" not in sql


def test_admin_tickets_ward_filter_applied_to_sql(client, mock_db):
    _conn, cursor = mock_db
    r = client.get("/admin/tickets?ward_id=20", headers=_auth("office", "secret"))
    assert r.status_code == 200
    sql = cursor.execute.call_args_list[0].args[0]
    args = cursor.execute.call_args_list[0].args[1]
    assert "ward_id = %s" in sql
    assert 20 in args


def test_admin_tickets_limit_capped(client, mock_db):
    """limit > 500 should be rejected (FastAPI Query validation)."""
    r = client.get("/admin/tickets?limit=999", headers=_auth("office", "secret"))
    assert r.status_code == 422


def test_admin_tickets_renders_empty_state(client):
    """When fetchall returns nothing, the empty-state placeholder shows."""
    import db
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.side_effect = [[], []]  # no rows, no counts
    conn = MagicMock()
    conn.cursor = MagicMock(return_value=cursor)

    with patch.object(db, "get_connection", return_value=conn):
        r = client.get("/admin/tickets", headers=_auth("office", "secret"))
    assert r.status_code == 200
    assert "No tickets match this filter" in r.text
