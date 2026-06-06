"""Meta WhatsApp Cloud API helpers.

Mirrors the patterns used in `jantrabot/cloud_api.py`. All sends are best-effort:
they return a boolean and log failures so the webhook can keep flowing.

Env vars consumed:
  META_GRAPH_API_VERSION    e.g. v21.0
  META_PHONE_NUMBER_ID      sender number ID
  META_WHATSAPP_TOKEN       permanent system-user token
  META_APP_SECRET           for inbound signature verification
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import requests


_GRAPH_VERSION = os.environ.get("META_GRAPH_API_VERSION", "v21.0")
_PHONE_NUMBER_ID = os.environ.get("META_PHONE_NUMBER_ID", "")
_TOKEN = os.environ.get("META_WHATSAPP_TOKEN", "")
_APP_SECRET = os.environ.get("META_APP_SECRET", "")
_TIMEOUT = 15


def _messages_url() -> str:
    return f"https://graph.facebook.com/{_GRAPH_VERSION}/{_PHONE_NUMBER_ID}/messages"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_TOKEN}",
        "Content-Type": "application/json",
    }


def _post(payload: dict) -> tuple[bool, dict]:
    try:
        r = requests.post(_messages_url(), headers=_headers(),
                          data=json.dumps(payload), timeout=_TIMEOUT)
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}
        if r.status_code >= 400:
            print(f"[CloudAPI] POST failed status={r.status_code} body={body}", flush=True)
            return False, body
        return True, body
    except Exception as e:
        print(f"[CloudAPI] POST exception: {type(e).__name__}: {e}", flush=True)
        return False, {"error": str(e)}


# ─── Signature verification (inbound webhook) ───────────────────────────────

def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Verify the X-Hub-Signature-256 header against META_APP_SECRET."""
    if not _APP_SECRET or not signature_header:
        # If app secret is unset (e.g. local dev), skip verification but warn.
        if not _APP_SECRET:
            print("[CloudAPI] META_APP_SECRET unset — skipping signature check", flush=True)
            return True
        return False
    expected = "sha256=" + hmac.new(
        _APP_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ─── Send helpers ───────────────────────────────────────────────────────────

def send_text(to: str, text: str, preview_url: bool = False) -> bool:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": bool(preview_url), "body": text[:4096]},
    }
    ok, _ = _post(payload)
    return ok


def send_buttons(
    to: str,
    body_text: str,
    buttons: list[dict],
    header_text: str | None = None,
    footer_text: str | None = None,
) -> bool:
    """Send up to 3 reply buttons. buttons = [{"id": "...", "title": "..."}, ...]"""
    interactive: dict = {
        "type": "button",
        "body": {"text": body_text[:1024]},
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {
                        "id": b["id"][:256],
                        "title": b["title"][:20],
                    },
                }
                for b in buttons[:3]
            ],
        },
    }
    if header_text:
        interactive["header"] = {"type": "text", "text": header_text[:60]}
    if footer_text:
        interactive["footer"] = {"text": footer_text[:60]}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }
    ok, _ = _post(payload)
    return ok


def send_list(
    to: str,
    body_text: str,
    button_text: str,
    sections: list[dict],
    header_text: str | None = None,
    footer_text: str | None = None,
) -> bool:
    """Send an interactive list-picker.

    sections = [{
        "title": "Wards",
        "rows": [{"id": "...", "title": "...", "description": "..."}, ...]
    }]
    """
    interactive: dict = {
        "type": "list",
        "body": {"text": body_text[:4096]},
        "action": {
            "button": button_text[:20],
            "sections": sections,
        },
    }
    if header_text:
        interactive["header"] = {"type": "text", "text": header_text[:60]}
    if footer_text:
        interactive["footer"] = {"text": footer_text[:60]}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }
    ok, _ = _post(payload)
    return ok


def send_image_by_id(to: str, media_id: str, caption: str | None = None) -> bool:
    image: dict = {"id": media_id}
    if caption:
        image["caption"] = caption[:1024]
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": image,
    }
    ok, _ = _post(payload)
    return ok


def mark_read(message_id: str) -> bool:
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    ok, _ = _post(payload)
    return ok


# ─── Inbound parsing helpers ────────────────────────────────────────────────

def extract_message(value: dict) -> dict | None:
    """Pull the first message dict out of an entry.changes[*].value payload."""
    msgs = value.get("messages") or []
    return msgs[0] if msgs else None


def message_text(msg: dict) -> str:
    t = msg.get("type")
    if t == "text":
        return (msg.get("text") or {}).get("body", "")
    if t == "interactive":
        inter = msg.get("interactive") or {}
        if inter.get("type") == "button_reply":
            return (inter.get("button_reply") or {}).get("id", "")
        if inter.get("type") == "list_reply":
            return (inter.get("list_reply") or {}).get("id", "")
    if t == "button":
        return (msg.get("button") or {}).get("payload", "")
    return ""


def message_kind(msg: dict) -> str:
    """Return one of: text | interactive | audio | image | document | video | other."""
    return msg.get("type") or "other"


def media_id(msg: dict) -> str | None:
    """Extract the media ID from an inbound media message."""
    t = msg.get("type")
    if t in ("image", "audio", "video", "document"):
        return (msg.get(t) or {}).get("id")
    return None
