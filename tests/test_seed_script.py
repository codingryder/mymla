"""Sanity tests for scripts/seed_demo_data.py.

The script is fire-and-forget against a real Neon DB; here we just verify the
row generator produces a sane 7-day schedule and that the seed functions issue
the expected DELETE / INSERT calls when `--reset` is passed.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

# Make the scripts/ folder importable.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

import seed_demo_data as seed  # noqa: E402


@pytest.fixture
def fake_db_conn():
    """Provide a MagicMock psycopg2 connection so seed_* funcs don't hit a real DB."""
    import db

    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor = MagicMock(return_value=cursor)

    with patch.object(db, "get_connection", return_value=conn):
        yield conn, cursor


def test_schedule_rows_cover_next_seven_days():
    today = date(2026, 6, 16)
    rows = seed._schedule_rows(today)

    assert len(rows) == 7
    assert rows[0][0] == today
    assert rows[-1][0] == date(2026, 6, 22)
    for event_date, title, venue, is_public in rows:
        assert isinstance(event_date, date)
        assert title and isinstance(title, str)
        assert venue and isinstance(venue, str)
        assert is_public is True


def test_seed_location_with_reset_deletes_then_upserts(fake_db_conn):
    conn, cursor = fake_db_conn

    seed.seed_location(reset=True)

    executed = [c.args[0] for c in cursor.execute.call_args_list]
    assert any("DELETE FROM mla_location" in sql for sql in executed)
    assert any("INSERT INTO mla_location" in sql for sql in executed)
    assert conn.commit.called


def test_seed_location_without_reset_skips_delete(fake_db_conn):
    conn, cursor = fake_db_conn

    seed.seed_location(reset=False)

    executed = [c.args[0] for c in cursor.execute.call_args_list]
    assert not any("DELETE FROM mla_location" in sql for sql in executed)
    assert any("INSERT INTO mla_location" in sql for sql in executed)


def test_seed_schedule_inserts_seven_rows(fake_db_conn):
    conn, cursor = fake_db_conn

    seed.seed_schedule(reset=False)

    assert cursor.executemany.called
    _sql, rowset = cursor.executemany.call_args.args
    assert len(rowset) == 7
    for row in rowset:
        assert len(row) == 4
    assert conn.commit.called


def test_seed_schedule_with_reset_deletes_first(fake_db_conn):
    conn, cursor = fake_db_conn

    seed.seed_schedule(reset=True)

    executed = [c.args[0] for c in cursor.execute.call_args_list]
    assert any("DELETE FROM mla_schedule" in sql for sql in executed)
    assert cursor.executemany.called
