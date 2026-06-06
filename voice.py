"""Sarvam AI speech-to-text wrapper for Malayalam + English voice notes.

Mirrors jantrabot's `_transcribe_voice` pattern. The Sarvam saarika:v2.5 model
covers both ml-IN and en-IN, so a single model handles MyMLA's two supported
languages.
"""

from __future__ import annotations

import os

import requests


_SARVAM_URL = "https://api.sarvam.ai/speech-to-text"
_SARVAM_KEY = os.environ.get("SARVAM_API_KEY", "")
_TIMEOUT = 30

_LANG_CODE = {"mal": "ml-IN", "eng": "en-IN"}
_MODEL = "saarika:v2.5"

_EXT_BY_MIME = {
    "audio/ogg":      "ogg",
    "audio/ogg; codecs=opus": "ogg",
    "audio/opus":     "ogg",
    "audio/mpeg":     "mp3",
    "audio/mp3":      "mp3",
    "audio/wav":      "wav",
    "audio/x-wav":    "wav",
    "audio/aac":      "aac",
    "audio/mp4":      "m4a",
    "audio/amr":      "amr",
}


def transcribe(audio_bytes: bytes, mime_type: str, lang: str) -> tuple[str | None, str]:
    """Return (transcript, error_kind). error_kind ∈ {"", "config", "transcription"}."""
    if not _SARVAM_KEY:
        print("[Voice] SARVAM_API_KEY unset", flush=True)
        return None, "config"
    sarvam_lang = _LANG_CODE.get(lang, "ml-IN")
    clean_mime = (mime_type or "audio/ogg").split(";")[0].strip()
    ext = _EXT_BY_MIME.get(clean_mime, "ogg")
    try:
        r = requests.post(
            _SARVAM_URL,
            headers={"api-subscription-key": _SARVAM_KEY},
            files={"file": (f"voice.{ext}", audio_bytes, clean_mime)},
            data={"language_code": sarvam_lang, "model": _MODEL},
            timeout=_TIMEOUT,
        )
        if r.status_code >= 400:
            print(
                f"[Voice] Sarvam status={r.status_code} body={r.text[:200]}",
                flush=True,
            )
            return None, "transcription"
        body = r.json()
        text = (body.get("transcript") or "").strip()
        if not text:
            return None, "transcription"
        return text, ""
    except Exception as e:
        print(f"[Voice] Sarvam exception: {type(e).__name__}: {e}", flush=True)
        return None, "transcription"
