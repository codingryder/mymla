"""Test bootstrap — mocks DB + outbound HTTP before any module is imported."""

import os
import sys
from unittest.mock import MagicMock, patch

# Make project root importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Required env vars so module-level reads don't blow up.
os.environ.setdefault("NEON_DSN",                   "postgresql://fake@localhost/fake")
os.environ.setdefault("META_APP_SECRET",            "")  # signature verify skipped when blank
os.environ.setdefault("META_WHATSAPP_TOKEN",        "fake-token")
os.environ.setdefault("META_PHONE_NUMBER_ID",       "000000000000000")
os.environ.setdefault("META_WEBHOOK_VERIFY_TOKEN",  "fake-verify")
os.environ.setdefault("SARVAM_API_KEY",             "fake-sarvam")
os.environ.setdefault("SENDGRID_API_KEY",           "")

# Patch psycopg2 connection so importing db.py is harmless.
_fake_cursor = MagicMock()
_fake_cursor.__enter__ = MagicMock(return_value=_fake_cursor)
_fake_cursor.__exit__  = MagicMock(return_value=False)
_fake_cursor.rowcount  = 0
_fake_cursor.fetchone  = MagicMock(return_value=None)
_fake_cursor.fetchall  = MagicMock(return_value=[])

_fake_conn = MagicMock()
_fake_conn.closed = False
_fake_conn.cursor = MagicMock(return_value=_fake_cursor)

with patch("psycopg2.connect", return_value=_fake_conn):
    import db  # noqa: F401
    import cloud_api  # noqa: F401
