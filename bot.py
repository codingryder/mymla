"""MyMLA WhatsApp Chatbot — FastAPI app + Meta Cloud webhook.

Inbound flow:
  GET  /webhook   verify Meta subscription challenge
  POST /webhook   ack 200 fast, dispatch real work in a background task

The dispatcher pulls the inbound `messages[0]` from the payload, resolves the
user row, applies the 30-minute session reset guard, then hands off to
`handlers.dispatch`.
"""

from __future__ import annotations

import os
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()  # populate os.environ before any module reads it

from fastapi import BackgroundTasks, FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse, PlainTextResponse  # noqa: E402

import cloud_api  # noqa: E402
import db  # noqa: E402
import handlers  # noqa: E402
import session as session_mod  # noqa: E402
import strings as S  # noqa: E402


app = FastAPI(title="MyMLA WhatsApp Chatbot")


# ─── Startup ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    try:
        db.ensure_schema()
    except Exception as e:
        print(f"[Startup] ensure_schema failed: {type(e).__name__}: {e}", flush=True)


# ─── Timing middleware ─────────────────────────────────────────────────────

@app.middleware("http")
async def timing(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(
        f"[Timing] {request.method} {request.url.path} "
        f"status={response.status_code} total_ms={elapsed_ms:.0f}",
        flush=True,
    )
    return response


# ─── Healthcheck ────────────────────────────────────────────────────────────

@app.get("/")
async def root() -> dict:
    return {"service": "mymla-bot", "ok": True}


# ─── Webhook verification (GET) ─────────────────────────────────────────────

@app.get("/webhook")
async def webhook_verify(request: Request):
    """Meta calls GET /webhook?hub.mode=subscribe&hub.verify_token=...&hub.challenge=..."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    expected = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "")
    if mode == "subscribe" and token and token == expected:
        return PlainTextResponse(challenge)
    return PlainTextResponse("forbidden", status_code=403)


# ─── Webhook inbound (POST) ─────────────────────────────────────────────────

@app.post("/webhook")
async def webhook_inbound(request: Request, background_tasks: BackgroundTasks):
    raw = await request.body()
    sig = request.headers.get("x-hub-signature-256")
    if not cloud_api.verify_signature(raw, sig):
        return JSONResponse({"ok": False, "error": "bad signature"}, status_code=403)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    background_tasks.add_task(_process_payload, payload)
    return JSONResponse({"ok": True})


def _process_payload(payload: dict[str, Any]) -> None:
    try:
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                msg = cloud_api.extract_message(value)
                if not msg:
                    continue
                _handle_message(msg)
    except Exception as e:
        print(f"[Webhook] processing failed: {type(e).__name__}: {e}", flush=True)


def _handle_message(msg: dict) -> None:
    phone = (msg.get("from") or "").strip()
    if not phone:
        return

    is_new = db.is_new_user(phone)
    user = db.get_user(phone) or {"phone": phone}

    print(
        f"[Webhook] phone=...{phone[-4:]} new={is_new} "
        f"kind={cloud_api.message_kind(msg)} step={user.get('current_step')} "
        f"flow={user.get('pending_flow')} onboarded={user.get('onboarding_complete')}",
        flush=True,
    )

    if session_mod.reset_if_expired(user):
        lang = user.get("preferred_language") or S.DEFAULT_LANG
        if user.get("onboarding_complete"):
            cloud_api.send_text(phone, S.t(lang, "session_reset_notice"))
            user = db.get_user(phone) or user
            handlers.menu.start(phone, lang)
            return
        # Onboarding wasn't finished — restart it from scratch.
        user = db.get_user(phone) or user

    # New user with no language yet → kick off Phase 1.
    if not user.get("preferred_language") and not user.get("current_step"):
        handlers.onboarding.start(phone)
        return

    handlers.dispatch(phone, user, msg)


# Best-effort message-status callback (we don't act on it, just log).
@app.post("/webhook/status")
async def webhook_status(request: Request):
    return JSONResponse({"ok": True})
