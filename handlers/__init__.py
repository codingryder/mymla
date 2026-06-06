"""Handler dispatch.

Each flow module exposes:
  - start(phone, lang)               sends the first prompt
  - handle(phone, lang, user, msg)   advances the flow based on inbound msg

`dispatch` is the single entry point the webhook calls per inbound message.
"""

from __future__ import annotations

import cloud_api
import db
import strings as S

from . import complaint, event, location, meeting, menu, onboarding, schedule


# step prefix → handler module
_STEP_PREFIX = {
    "await_lang":           onboarding,
    "await_aadhaar":        onboarding,
    "await_ward":           onboarding,
    "await_booth":          onboarding,
    "await_pin":            onboarding,
    "complaint_":           complaint,
    "meeting_":             meeting,
    "event_":               event,
}


def _route_to_module(step: str | None):
    if not step:
        return None
    if step in _STEP_PREFIX:
        return _STEP_PREFIX[step]
    for prefix, mod in _STEP_PREFIX.items():
        if step.startswith(prefix):
            return mod
    return None


def dispatch(phone: str, user: dict, msg: dict) -> None:
    lang = user.get("preferred_language") or S.DEFAULT_LANG
    text = (cloud_api.message_text(msg) or "").strip()

    # Global escape hatch — typing "menu" / "home" jumps back to the hub.
    if text.lower() in {"menu", "home", "/menu", "/start"} and user.get("onboarding_complete"):
        db.set_field(phone, current_step=None, pending_flow=None, session_data={})
        menu.start(phone, lang)
        return

    # Resume an in-flight flow.
    step = user.get("current_step")
    mod = _route_to_module(step)
    if mod is not None:
        mod.handle(phone, lang, user, msg)
        return

    # Onboarding still in progress (no current_step but profile incomplete).
    if not user.get("onboarding_complete"):
        onboarding.resume(phone, user)
        return

    # Idle, onboarded user — interpret the message.
    if msg.get("type") == "interactive":
        # List/button reply that doesn't match a known step → probably a menu pick.
        menu.handle_menu_selection(phone, lang, text)
        return

    # Plain text from an idle user → show the menu.
    menu.start(phone, lang)
