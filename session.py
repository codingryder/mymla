"""Session retention guard per BRD §2.

If the user is inactive for ≥ SESSION_TIMEOUT_MINUTES (default 30), the next
inbound resets `current_step`, `pending_flow` and `session_data` and routes
them back to the Welcome / Main Menu node. The persisted profile (lang, ward,
booth, PIN) is preserved across timeouts.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import db


def _timeout_minutes() -> int:
    try:
        return int(os.environ.get("SESSION_TIMEOUT_MINUTES", "30"))
    except ValueError:
        return 30


def is_expired(user_row: dict) -> bool:
    last = user_row.get("session_last_active")
    if not last:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age_min = (datetime.now(timezone.utc) - last).total_seconds() / 60
    return age_min >= _timeout_minutes()


def reset_if_expired(user_row: dict) -> bool:
    """If the user's session has timed out, soft-reset state and return True."""
    if not user_row:
        return False
    if is_expired(user_row):
        db.reset_session(user_row["phone"], hard=False)
        print(
            f"[Session] reset for {user_row['phone'][-4:]} after timeout",
            flush=True,
        )
        return True
    return False
