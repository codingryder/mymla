"""Postgres (Neon) state layer for MyMLA.

Schema and helpers for:
  - mymla_users           per-citizen profile + active session state
  - mymla_complaints      ticketed grievances
  - mymla_meetings        appointment requests
  - mymla_event_invites   public-event invitations
  - mla_schedule          MLA's upcoming public program chart (read-only)
  - mla_location          MLA's current location card (single-row, read-only)

Modeled on jantrabot's `db.py`: single global psycopg2 connection with TCP keepalives,
statement timeout, and lazy reconnect.
"""

from __future__ import annotations

import json
import os
import random
import string
from datetime import datetime, timezone
from typing import Any

import psycopg2
import psycopg2.extras


# ─── Connection management ──────────────────────────────────────────────────

_CONNECT_TIMEOUT_S = 10
_STATEMENT_TIMEOUT_MS = 30_000

_conn: psycopg2.extensions.connection | None = None


def _dsn() -> str:
    dsn = os.environ.get("NEON_DSN", "")
    if not dsn:
        raise RuntimeError("NEON_DSN env var is not set")
    return dsn


def get_connection() -> psycopg2.extensions.connection:
    global _conn
    if _conn is not None and not _conn.closed:
        return _conn
    _conn = psycopg2.connect(
        _dsn(),
        connect_timeout=_CONNECT_TIMEOUT_S,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
        options=f"-c statement_timeout={_STATEMENT_TIMEOUT_MS}",
    )
    _conn.autocommit = False
    return _conn


# ─── Schema ─────────────────────────────────────────────────────────────────

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS mymla_users (
    phone                  TEXT PRIMARY KEY,
    joined_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    preferred_language     TEXT,
    aadhaar_number         TEXT,
    ward_id                INTEGER,
    booth_number           INTEGER,
    pin_code               TEXT,
    onboarding_complete    BOOLEAN NOT NULL DEFAULT FALSE,
    current_step           TEXT,
    pending_flow           TEXT,
    session_data           JSONB NOT NULL DEFAULT '{}'::jsonb,
    session_last_active    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mymla_complaints (
    ticket_id              TEXT PRIMARY KEY,
    phone                  TEXT NOT NULL,
    ward_id                INTEGER,
    booth_number           INTEGER,
    category               TEXT,
    description_text       TEXT,
    description_voice_url  TEXT,
    image_media_ids        TEXT[] NOT NULL DEFAULT '{}',
    local_leader_ref       TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status                 TEXT NOT NULL DEFAULT 'OPEN'
);
CREATE INDEX IF NOT EXISTS idx_mymla_complaints_phone ON mymla_complaints (phone);

CREATE TABLE IF NOT EXISTS mymla_meetings (
    id                     SERIAL PRIMARY KEY,
    phone                  TEXT NOT NULL,
    agenda_category        TEXT,
    summary                TEXT,
    preferred_window       TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status                 TEXT NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS mymla_event_invites (
    id                     SERIAL PRIMARY KEY,
    phone                  TEXT NOT NULL,
    event_name             TEXT,
    event_when             TEXT,
    venue_address          TEXT,
    invite_asset_media_id  TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status                 TEXT NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS mla_schedule (
    id                     SERIAL PRIMARY KEY,
    event_date             DATE NOT NULL,
    title                  TEXT NOT NULL,
    venue                  TEXT,
    is_public              BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_mla_schedule_date ON mla_schedule (event_date);

CREATE TABLE IF NOT EXISTS mla_location (
    id                     INTEGER PRIMARY KEY DEFAULT 1,
    status_key             TEXT NOT NULL DEFAULT 'office',
    status_ward_id         INTEGER,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT mla_location_singleton CHECK (id = 1)
);
"""


def ensure_schema() -> None:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(SCHEMA_DDL)
        # seed mla_location singleton
        cur.execute(
            "INSERT INTO mla_location (id) VALUES (1) ON CONFLICT (id) DO NOTHING;"
        )
    conn.commit()
    print("[DB] schema ensured", flush=True)


# ─── User state helpers ─────────────────────────────────────────────────────

def is_new_user(phone: str) -> bool:
    """INSERT-on-conflict-do-nothing; return True iff this is a fresh row."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO mymla_users (phone) VALUES (%s) "
            "ON CONFLICT (phone) DO NOTHING",
            (phone,),
        )
        inserted = cur.rowcount == 1
    conn.commit()
    return inserted


def get_user(phone: str) -> dict | None:
    conn = get_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM mymla_users WHERE phone = %s", (phone,))
        row = cur.fetchone()
    return dict(row) if row else None


def set_field(phone: str, **fields: Any) -> None:
    if not fields:
        return
    keys = list(fields.keys())
    setters = ", ".join(f"{k} = %s" for k in keys)
    values = [
        json.dumps(fields[k]) if k == "session_data" else fields[k]
        for k in keys
    ]
    values.append(phone)
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE mymla_users SET {setters}, session_last_active = NOW() "
            f"WHERE phone = %s",
            values,
        )
    conn.commit()


def touch_session(phone: str) -> None:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE mymla_users SET session_last_active = NOW() WHERE phone = %s",
            (phone,),
        )
    conn.commit()


def reset_session(phone: str, *, hard: bool = False) -> None:
    """Clear current step + pending flow + scratch data, optionally wiping profile.

    `hard=True` is reserved for explicit user reset; the 30-min timeout uses soft.
    """
    fields = {
        "current_step": None,
        "pending_flow": None,
        "session_data": {},
    }
    if hard:
        fields.update({
            "preferred_language": None,
            "aadhaar_number": None,
            "ward_id": None,
            "booth_number": None,
            "pin_code": None,
            "onboarding_complete": False,
        })
    set_field(phone, **fields)


# ─── Complaint persistence ──────────────────────────────────────────────────

def generate_ticket_id(ward_id: int) -> str:
    """Format: MLA-GRI-WARD{NN}-{XXXXX} per BRD §6.5."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    ward_part = f"WARD{ward_id:02d}" if ward_id else "WARD00"
    return f"MLA-GRI-{ward_part}-{suffix}"


def insert_complaint(
    *,
    phone: str,
    ward_id: int | None,
    booth_number: int | None,
    category: str | None,
    description_text: str | None,
    description_voice_url: str | None,
    image_media_ids: list[str],
    local_leader_ref: str | None,
) -> str:
    """Insert with a freshly minted ticket id (retry once on collision)."""
    conn = get_connection()
    for _ in range(3):
        ticket_id = generate_ticket_id(ward_id or 0)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mymla_complaints
                        (ticket_id, phone, ward_id, booth_number, category,
                         description_text, description_voice_url,
                         image_media_ids, local_leader_ref)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ticket_id, phone, ward_id, booth_number, category,
                        description_text, description_voice_url,
                        image_media_ids, local_leader_ref,
                    ),
                )
            conn.commit()
            return ticket_id
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            continue
    raise RuntimeError("could not generate a unique ticket id after 3 attempts")


# ─── Meeting / event persistence ────────────────────────────────────────────

def insert_meeting(*, phone: str, agenda_category: str, summary: str,
                   preferred_window: str) -> int:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mymla_meetings (phone, agenda_category, summary, preferred_window)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (phone, agenda_category, summary, preferred_window),
        )
        meeting_id = cur.fetchone()[0]
    conn.commit()
    return meeting_id


def insert_event_invite(*, phone: str, event_name: str, event_when: str,
                        venue_address: str, invite_asset_media_id: str | None) -> int:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mymla_event_invites
                (phone, event_name, event_when, venue_address, invite_asset_media_id)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
            (phone, event_name, event_when, venue_address, invite_asset_media_id),
        )
        event_id = cur.fetchone()[0]
    conn.commit()
    return event_id


# ─── MLA location + schedule (read-only for the citizen) ────────────────────

def get_mla_location() -> dict:
    conn = get_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM mla_location WHERE id = 1")
        row = cur.fetchone() or {
            "status_key": "office",
            "status_ward_id": None,
            "updated_at": datetime.now(timezone.utc),
        }
    return dict(row)


def get_mla_schedule_next_7_days() -> list[dict]:
    conn = get_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT event_date, title, venue
            FROM mla_schedule
            WHERE is_public = TRUE
              AND event_date >= CURRENT_DATE
              AND event_date <  CURRENT_DATE + INTERVAL '7 days'
            ORDER BY event_date ASC, id ASC
            """
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]
