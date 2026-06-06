"""SendGrid ops alerts with per-kind cooldown (mirrors jantrabot/alerts.py).

Each alert kind has a 60-minute cooldown so a flapping upstream cannot spam the
inbox. The cooldowns are stored in-process; on Render free-tier this resets on
every cold start, which is acceptable for ops paging.
"""

from __future__ import annotations

import os
import time

import requests


_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
_TO = os.environ.get("ALERT_EMAIL_TO", "")
_FROM = os.environ.get("ALERT_EMAIL_FROM", "alerts@example.com")
_COOLDOWN_S = 60 * 60

_last_sent: dict[str, float] = {}


def _on_cooldown(kind: str) -> bool:
    last = _last_sent.get(kind, 0.0)
    return (time.time() - last) < _COOLDOWN_S


def _send(subject: str, body: str, kind: str) -> bool:
    if not _API_KEY or not _TO:
        print(f"[Alerts] suppressed ({kind}) — SENDGRID_API_KEY/ALERT_EMAIL_TO unset", flush=True)
        return False
    if _on_cooldown(kind):
        print(f"[Alerts] suppressed ({kind}) — cooldown active", flush=True)
        return False
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{"to": [{"email": _TO}]}],
                "from": {"email": _FROM, "name": "MyMLA Bot Ops"},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}],
            },
            timeout=10,
        )
        if r.status_code >= 400:
            print(f"[Alerts] SendGrid status={r.status_code} body={r.text[:200]}", flush=True)
            return False
        _last_sent[kind] = time.time()
        print(f"[Alerts] sent kind={kind}", flush=True)
        return True
    except Exception as e:
        print(f"[Alerts] exception: {type(e).__name__}: {e}", flush=True)
        return False


def notify_db_failure(detail: str) -> bool:
    return _send(
        subject="[MyMLA] Postgres failure",
        body=f"Postgres operation failed.\n\n{detail}",
        kind="db_failure",
    )


def notify_meta_send_failure(detail: str) -> bool:
    return _send(
        subject="[MyMLA] Meta Cloud API send failure",
        body=f"Outbound WhatsApp send is failing.\n\n{detail}",
        kind="meta_send_failure",
    )


def notify_sarvam_failure(detail: str) -> bool:
    return _send(
        subject="[MyMLA] Sarvam STT failure",
        body=f"Voice transcription is failing.\n\n{detail}",
        kind="sarvam_failure",
    )
