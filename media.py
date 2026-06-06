"""Download inbound media (images, voice notes, documents) from Meta's Graph API.

Two-step process per Meta docs:
  1. GET /{media-id}      → JSON { "url": "<short-lived signed URL>", "mime_type": ... }
  2. GET <signed url>     → bytes (must include the bearer token)
"""

from __future__ import annotations

import os

import requests


_GRAPH_VERSION = os.environ.get("META_GRAPH_API_VERSION", "v21.0")
_TOKEN = os.environ.get("META_WHATSAPP_TOKEN", "")
_TIMEOUT = 20


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TOKEN}"}


def resolve_media(media_id: str) -> tuple[str | None, str | None]:
    """Return (download_url, mime_type) for an inbound media id, or (None, None)."""
    try:
        url = f"https://graph.facebook.com/{_GRAPH_VERSION}/{media_id}"
        r = requests.get(url, headers=_headers(), timeout=_TIMEOUT)
        if r.status_code >= 400:
            print(
                f"[Media] resolve {media_id} failed status={r.status_code} "
                f"body={r.text[:200]}",
                flush=True,
            )
            return None, None
        body = r.json()
        return body.get("url"), body.get("mime_type")
    except Exception as e:
        print(f"[Media] resolve exception: {type(e).__name__}: {e}", flush=True)
        return None, None


def download_bytes(signed_url: str) -> bytes | None:
    try:
        r = requests.get(signed_url, headers=_headers(), timeout=_TIMEOUT)
        if r.status_code >= 400:
            print(
                f"[Media] download failed status={r.status_code} body={r.text[:200]}",
                flush=True,
            )
            return None
        return r.content
    except Exception as e:
        print(f"[Media] download exception: {type(e).__name__}: {e}", flush=True)
        return None


def fetch_media(media_id: str) -> tuple[bytes | None, str | None]:
    """Convenience: one call returns (bytes, mime_type)."""
    signed_url, mime = resolve_media(media_id)
    if not signed_url:
        return None, None
    return download_bytes(signed_url), mime
