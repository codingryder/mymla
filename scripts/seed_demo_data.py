"""Seed `mla_location` + `mla_schedule` with demo content.

Lets the "Where is my MLA" and "Program Chart" menu options return real
content during real-phone smoke testing (Phase 1).

Usage (from repo root, with .env populated):

    PYTHONPATH=. python3 scripts/seed_demo_data.py
    PYTHONPATH=. python3 scripts/seed_demo_data.py --reset

`--reset` wipes the two tables before seeding so re-runs produce a clean,
predictable state. Without it, the script is idempotent for `mla_location`
(updates the singleton row) but APPENDS rows to `mla_schedule`.

Real data should replace this once the MLA's office supplies it — keep the
script around as the canonical "what does fresh demo data look like" reference.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()

import db  # noqa: E402  — env must be loaded first


# Default location to seed: meeting citizens at the constituency office.
DEFAULT_LOCATION = {"status_key": "office", "status_ward_id": None}


def _schedule_rows(today: date) -> list[tuple[date, str, str, bool]]:
    """7 days of plausible public events, anchored on `today`."""
    return [
        (today + timedelta(days=0), "Morning citizen meeting",
         "MLA Constituency Office, Vanchiyoor", True),
        (today + timedelta(days=1), "Ward 12 drainage inspection",
         "Valiyathura beach road junction", True),
        (today + timedelta(days=2), "Legislative Assembly Session",
         "Niyamasabha Mandiram, Thiruvananthapuram", True),
        (today + timedelta(days=3), "Anganwadi inauguration",
         "Kannanthura Community Hall (Ward 15)", True),
        (today + timedelta(days=4), "Public grievance day",
         "MLA Constituency Office, Vanchiyoor", True),
        (today + timedelta(days=5), "Town hall on coastal erosion",
         "Beemapally Fishermen's Hall (Ward 9)", True),
        (today + timedelta(days=6), "Ward 20 site visit — drinking water",
         "Thampanoor circle near Central Railway Station", True),
    ]


def seed_location(reset: bool) -> None:
    conn = db.get_connection()
    with conn.cursor() as cur:
        if reset:
            cur.execute("DELETE FROM mla_location;")
        cur.execute(
            """
            INSERT INTO mla_location (id, status_key, status_ward_id, updated_at)
            VALUES (1, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE
            SET status_key = EXCLUDED.status_key,
                status_ward_id = EXCLUDED.status_ward_id,
                updated_at = NOW();
            """,
            (DEFAULT_LOCATION["status_key"], DEFAULT_LOCATION["status_ward_id"]),
        )
    conn.commit()
    print(f"[Seed] mla_location set to status_key='{DEFAULT_LOCATION['status_key']}'")


def seed_schedule(reset: bool) -> None:
    today = date.today()
    rows = _schedule_rows(today)
    conn = db.get_connection()
    with conn.cursor() as cur:
        if reset:
            cur.execute("DELETE FROM mla_schedule;")
        cur.executemany(
            """
            INSERT INTO mla_schedule (event_date, title, venue, is_public)
            VALUES (%s, %s, %s, %s);
            """,
            rows,
        )
    conn.commit()
    print(f"[Seed] mla_schedule rows inserted: {len(rows)} "
          f"(window {rows[0][0]} → {rows[-1][0]})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo mla_location + mla_schedule rows.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing rows in both tables before seeding.",
    )
    parser.add_argument(
        "--only",
        choices=("location", "schedule"),
        help="Seed only one of the two tables.",
    )
    args = parser.parse_args()

    db.ensure_schema()

    if args.only in (None, "location"):
        seed_location(reset=args.reset)
    if args.only in (None, "schedule"):
        seed_schedule(reset=args.reset)

    print("[Seed] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
