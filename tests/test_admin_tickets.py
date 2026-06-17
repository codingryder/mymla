"""Phase 3.1 — admin ticket viewer + dashboard home (HTTP Basic Auth, fail-closed)."""

from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timezone, date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "office")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    import bot
    # follow_redirects=False so we can assert 307/303 directly.
    return TestClient(bot.app, follow_redirects=False)


@pytest.fixture
def client_unconfigured(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "")
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    import bot
    return TestClient(bot.app, follow_redirects=False)


def _auth(user: str, pw: str) -> dict[str, str]:
    """HTTP Basic Auth header (still supported as a fallback for scripts/curl)."""
    token = b64encode(f"{user}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _login(client) -> None:
    """POST the login form so the test client picks up the session cookie."""
    r = client.post(
        "/admin/login",
        data={"username": "office", "password": "secret", "next": "/admin/"},
    )
    assert r.status_code == 303, f"expected login to redirect, got {r.status_code}"


# ─── Shared row fixtures ────────────────────────────────────────────────────

@pytest.fixture
def fake_complaints():
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


def _mock_conn(execute_returns: list):
    """Return (conn, cursor) where each cursor.execute → corresponding fetchall result.

    Spare calls return [] so we don't have to count exact queries per route.
    """
    import db

    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.side_effect = list(execute_returns) + [[]] * 100  # generous tail

    conn = MagicMock()
    conn.cursor = MagicMock(return_value=cursor)
    return conn, cursor


@pytest.fixture
def mock_db_tickets(fake_complaints):
    """For /admin/tickets: 2 queries (fetch_tickets, fetch_counts_by_status)."""
    import db
    conn, cursor = _mock_conn([
        list(fake_complaints),                         # fetch_tickets rows
        [{"status": "OPEN", "n": 5},                   # counts_by_status
         {"status": "IN_PROGRESS", "n": 2},
         {"status": "RESOLVED", "n": 9}],
    ])
    with patch.object(db, "get_connection", return_value=conn):
        yield conn, cursor


@pytest.fixture
def mock_db_home(fake_complaints):
    """For /admin/: status counts, by-category, top-wards, daily, citizens, resolved-7d, latest tickets."""
    import db
    conn, cursor = _mock_conn([
        [{"status": "OPEN", "n": 12},                  # counts_by_status
         {"status": "IN_PROGRESS", "n": 3},
         {"status": "RESOLVED", "n": 9}],
        [{"n": 7}],                                    # resolved_last_n_days
        [{"n": 47}],                                   # citizen_count
        [{"category": "Drinking Water", "n": 8},       # counts_by_category
         {"category": "Road", "n": 6},
         {"category": "Waste", "n": 5}],
        [{"ward_id": 20, "n": 12},                     # top_wards
         {"ward_id": 14, "n": 4}],
        [{"d": date(2026, 6, 16), "n": 3},             # daily_counts
         {"d": date(2026, 6, 17), "n": 5}],
        list(fake_complaints),                         # latest tickets
    ])
    with patch.object(db, "get_connection", return_value=conn):
        yield conn, cursor


# ─── Auth ───────────────────────────────────────────────────────────────────

def test_unauthenticated_admin_request_redirects_to_login(client):
    """No cookie, no Basic Auth → 307 to the styled login page."""
    r = client.get("/admin/tickets")
    assert r.status_code == 307
    assert r.headers.get("location") == "/admin/login"


def test_admin_returns_503_when_env_not_configured(client_unconfigured):
    r = client_unconfigured.get("/admin/tickets", headers=_auth("anything", "anything"))
    assert r.status_code == 503


# ─── Backwards-compat: HTTP Basic still works for scripts/curl ──────────────

def test_basic_auth_with_correct_credentials_still_works(client, mock_db_tickets):
    r = client.get("/admin/tickets", headers=_auth("office", "secret"))
    assert r.status_code == 200


def test_basic_auth_with_wrong_credentials_redirects_to_login(client):
    r = client.get("/admin/tickets", headers=_auth("office", "WRONG"))
    assert r.status_code == 307
    assert r.headers["location"] == "/admin/login"


# ─── Login form ─────────────────────────────────────────────────────────────

def test_login_get_renders_styled_form(client):
    r = client.get("/admin/login")
    assert r.status_code == 200
    body = r.text
    # Form fields
    assert 'name="username"' in body
    assert 'name="password"' in body
    assert 'name="next"' in body
    # Styled with the Civic Vellum theme (seal + brand)
    assert "/assets/mymla_profile_512.png" in body
    assert "Office Console" in body


def test_login_get_503_when_admin_env_unset(client_unconfigured):
    r = client_unconfigured.get("/admin/login")
    assert r.status_code == 503


def test_login_post_with_good_credentials_sets_cookie_and_redirects(client):
    r = client.post(
        "/admin/login",
        data={"username": "office", "password": "secret", "next": "/admin/"},
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/"
    # Cookie was set on the test client.
    assert "mymla_admin_session" in client.cookies


def test_login_post_with_bad_credentials_returns_401_with_error_text(client):
    r = client.post(
        "/admin/login",
        data={"username": "office", "password": "WRONG", "next": "/admin/"},
    )
    assert r.status_code == 401
    assert "Invalid username or password" in r.text
    # No cookie was set.
    assert "mymla_admin_session" not in client.cookies


def test_login_post_rejects_external_next_path(client):
    """`next` must point inside /admin to prevent open redirects."""
    r = client.post(
        "/admin/login",
        data={"username": "office", "password": "secret",
              "next": "https://evil.example.com/"},
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/"


# ─── Session cookie auth ────────────────────────────────────────────────────

def test_authenticated_request_with_session_cookie_returns_200(client, mock_db_tickets):
    _login(client)
    r = client.get("/admin/tickets")
    assert r.status_code == 200


def test_logout_clears_cookie_and_redirects_to_login(client):
    _login(client)
    assert "mymla_admin_session" in client.cookies
    r = client.get("/admin/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"
    assert "mymla_admin_session" not in client.cookies


def test_login_get_skips_form_when_already_signed_in(client):
    _login(client)
    r = client.get("/admin/login")
    # Already authenticated → 303 to default /admin/
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/"


# ─── Layout / sidebar ───────────────────────────────────────────────────────

def test_admin_home_renders_with_sidebar_and_logo(client, mock_db_home):
    r = client.get("/admin/", headers=_auth("office", "secret"))
    assert r.status_code == 200
    body = r.text
    # Brand seal referenced
    assert "/assets/mymla_profile_512.png" in body
    # Sidebar nav items present
    assert ">Home<" in body
    assert ">Tickets<" in body
    assert ">Meetings<" in body
    assert ">Schedule<" in body
    # Active nav highlight
    assert 'class="active"' in body
    # Signed-in label
    assert "office" in body


def test_admin_tickets_renders_inside_layout(client, mock_db_tickets):
    r = client.get("/admin/tickets", headers=_auth("office", "secret"))
    assert r.status_code == 200
    body = r.text
    assert "/assets/mymla_profile_512.png" in body  # sidebar present
    assert ">Tickets<" in body


def test_layout_includes_mobile_drawer_toggle(client, mock_db_home):
    """Hamburger + checkbox + overlay are present so mobile drawer works without JS."""
    r = client.get("/admin/", headers=_auth("office", "secret"))
    body = r.text
    assert 'id="nav-toggle"' in body
    assert 'class="nav-overlay"' in body
    assert 'class="hamburger"' in body
    assert 'class="mobile-header"' in body
    # The overlay label and hamburger label both target the same checkbox.
    assert body.count('for="nav-toggle"') >= 2


# ─── Dashboard home — KPIs + charts ─────────────────────────────────────────

def test_home_renders_kpi_numbers(client, mock_db_home):
    r = client.get("/admin/", headers=_auth("office", "secret"))
    body = r.text
    # Labels
    assert "Open tickets" in body
    assert "In progress" in body
    assert "Resolved (7d)" in body
    assert "Citizens onboarded" in body
    # KPI values rendered (from the mock DB)
    assert ">12<" in body  # open count
    assert ">3<" in body   # in_progress
    assert ">7<" in body   # resolved last 7d
    assert ">47<" in body  # citizen count


def test_home_renders_charts_with_data(client, mock_db_home):
    r = client.get("/admin/", headers=_auth("office", "secret"))
    body = r.text
    # Category labels appear in the bar chart section
    assert "Drinking Water" in body
    assert "Road" in body
    # Top-ward chart resolves the ward name from wards.py
    assert "Thampanoor" in body  # ward 20
    assert "Vettukaud" in body   # ward 14
    # Sparkline SVG is present
    assert "<svg" in body
    assert "</svg>" in body


def test_home_empty_state_renders_when_no_data(client):
    """All queries return empty → charts show empty-state copy, sparkline gracefully degrades."""
    import db
    conn, _cursor = _mock_conn([])  # everything empty
    with patch.object(db, "get_connection", return_value=conn):
        r = client.get("/admin/", headers=_auth("office", "secret"))
    assert r.status_code == 200
    body = r.text
    assert "No tickets in the last 30 days" in body
    assert "No tickets with a ward yet" in body
    assert "No tickets filed yet." in body
    # KPIs default to 0
    assert ">0<" in body


# ─── Tickets viewer ─────────────────────────────────────────────────────────

def test_admin_tickets_renders_rows(client, mock_db_tickets, fake_complaints):
    r = client.get("/admin/tickets", headers=_auth("office", "secret"))
    assert r.status_code == 200
    body = r.text
    for row in fake_complaints:
        assert row["ticket_id"] in body
    assert "status-OPEN" in body
    assert "status-IN_PROGRESS" in body
    # Filter-bar counts from the second cursor.fetchall()
    assert ">5<" in body   # OPEN
    assert ">16<" in body  # ALL = 5+2+9
    # Media indicators
    assert "📷" in body
    assert "🎙" in body


def test_admin_tickets_status_filter_applied_to_sql(client, mock_db_tickets):
    _conn, cursor = mock_db_tickets
    r = client.get("/admin/tickets?status=RESOLVED", headers=_auth("office", "secret"))
    assert r.status_code == 200
    sql = cursor.execute.call_args_list[0].args[0]
    args = cursor.execute.call_args_list[0].args[1]
    assert "status = %s" in sql
    assert "RESOLVED" in args


def test_admin_tickets_status_all_means_no_status_filter(client, mock_db_tickets):
    _conn, cursor = mock_db_tickets
    r = client.get("/admin/tickets?status=ALL", headers=_auth("office", "secret"))
    assert r.status_code == 200
    sql = cursor.execute.call_args_list[0].args[0]
    assert "status = %s" not in sql


def test_admin_tickets_ward_filter_applied_to_sql(client, mock_db_tickets):
    _conn, cursor = mock_db_tickets
    r = client.get("/admin/tickets?ward_id=20", headers=_auth("office", "secret"))
    assert r.status_code == 200
    sql = cursor.execute.call_args_list[0].args[0]
    args = cursor.execute.call_args_list[0].args[1]
    assert "ward_id = %s" in sql
    assert 20 in args


def test_admin_tickets_limit_capped(client, mock_db_tickets):
    r = client.get("/admin/tickets?limit=999", headers=_auth("office", "secret"))
    assert r.status_code == 422


def test_admin_tickets_empty_state(client):
    import db
    conn, _cursor = _mock_conn([])  # no rows, no counts
    with patch.object(db, "get_connection", return_value=conn):
        r = client.get("/admin/tickets", headers=_auth("office", "secret"))
    assert r.status_code == 200
    assert "No tickets match this filter" in r.text
