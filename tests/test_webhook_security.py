"""Webhook signature verification + complaint image cap (BRD §2 + §6 Stage 3)."""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import patch

from tests.conftest import button_reply


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ─── Signature verification ─────────────────────────────────────────────────

def test_verify_signature_accepts_correctly_signed_payload(harness):
    import cloud_api

    secret = "s3cret-app-key"
    body = b'{"entry":[{"changes":[]}]}'
    with patch.object(cloud_api, "_APP_SECRET", secret):
        assert cloud_api.verify_signature(body, _sign(body, secret)) is True


def test_verify_signature_rejects_wrong_signature(harness):
    import cloud_api

    secret = "s3cret-app-key"
    body = b'{"entry":[{"changes":[]}]}'
    bad_sig = _sign(body, "wrong-secret")
    with patch.object(cloud_api, "_APP_SECRET", secret):
        assert cloud_api.verify_signature(body, bad_sig) is False


def test_verify_signature_rejects_tampered_body(harness):
    """Same secret, signature was computed for a different body → reject."""
    import cloud_api

    secret = "s3cret-app-key"
    body = b'{"entry":[{"changes":[]}]}'
    sig_for_other = _sign(b"{}", secret)
    with patch.object(cloud_api, "_APP_SECRET", secret):
        assert cloud_api.verify_signature(body, sig_for_other) is False


def test_verify_signature_rejects_missing_header_when_secret_set(harness):
    import cloud_api

    with patch.object(cloud_api, "_APP_SECRET", "s3cret-app-key"):
        assert cloud_api.verify_signature(b"{}", None) is False


def test_verify_signature_skips_when_secret_unset(harness):
    """Local-dev passthrough: empty META_APP_SECRET means accept anything (logged)."""
    import cloud_api

    with patch.object(cloud_api, "_APP_SECRET", ""):
        assert cloud_api.verify_signature(b"{}", None) is True
        assert cloud_api.verify_signature(b"{}", "sha256=anything") is True


# ─── Complaint image cap (5 max) ────────────────────────────────────────────

def _image_msg(media_id: str, sender: str) -> dict:
    return {"type": "image", "from": sender, "image": {"id": media_id, "mime_type": "image/jpeg"}}


def test_complaint_image_cap_rejects_sixth_image(harness):
    """5 images go in cleanly; the 6th triggers the over-cap notice and advances the flow."""
    store, outbox = harness
    import handlers

    phone = "919000000060"
    store.seed_onboarded_user(phone, lang="eng", ward_id=14, booth_number=4)

    # Step into the complaint flow up to the image stage.
    import tests.conftest as _c
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _c.list_reply("menu:complaint", sender=phone))
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _c.list_reply("cat:road", sender=phone))
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _c.text_msg("Pothole on the main road.", sender=phone))
    assert store.users[phone]["current_step"] == "complaint_images"

    # Send 5 images — each should be accepted and stored.
    for i in range(1, 6):
        user = store.get_user(phone)
        handlers.dispatch(phone, user, _image_msg(f"mid-{i}", phone))

    images_after_five = store.users[phone]["session_data"]["images"]
    assert images_after_five == [f"mid-{i}" for i in range(1, 6)]
    assert store.users[phone]["current_step"] == "complaint_images"

    # Send the 6th — must trigger the over-cap text, not be stored, and advance to leader_ref.
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _image_msg("mid-6", phone))

    # Image list unchanged — 6th was rejected.
    assert store.users[phone]["session_data"]["images"] == [f"mid-{i}" for i in range(1, 6)]
    # Flow advanced past the image stage.
    assert store.users[phone]["current_step"] == "complaint_leader_ref"

    # Over-cap notice was sent (English copy mentions the limit of 5).
    bodies = [e[1]["body"] for e in outbox.sent if e[0] == "text"]
    assert any("maximum limit of 5 images" in b.lower() or "5 images" in b.lower()
               for b in bodies), f"Expected over-cap notice in {bodies}"


def test_complaint_done_button_advances_before_cap(harness):
    """Citizen with fewer than 5 images can still click 'Done Uploading' and move on."""
    store, outbox = harness
    import handlers

    phone = "919000000061"
    store.seed_onboarded_user(phone, lang="eng", ward_id=14, booth_number=4)

    import tests.conftest as _c
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _c.list_reply("menu:complaint", sender=phone))
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _c.list_reply("cat:waste", sender=phone))
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _c.text_msg("Garbage pile not cleared for a week.", sender=phone))

    # 2 images, then Done
    for i in (1, 2):
        user = store.get_user(phone)
        handlers.dispatch(phone, user, _image_msg(f"mid-{i}", phone))
    user = store.get_user(phone)
    handlers.dispatch(phone, user, button_reply("complaint:done_images", sender=phone))

    assert store.users[phone]["current_step"] == "complaint_leader_ref"
    assert store.users[phone]["session_data"]["images"] == ["mid-1", "mid-2"]
