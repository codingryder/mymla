"""Event invitation flow state-machine test (BRD §7.3).

Menu → event → name → datetime → venue → asset (skip OR attach image) →
insert_event_invite fired, session cleared, success message sent.
"""

from tests.conftest import text_msg, button_reply, list_reply


def _image_msg(media_id: str, sender: str = "919000000020") -> dict:
    return {"type": "image", "from": sender, "image": {"id": media_id, "mime_type": "image/png"}}


def test_event_flow_skip_asset(harness):
    """Citizen invites the MLA to an event but doesn't attach an invitation card."""
    store, outbox = harness
    import handlers

    phone = "919000000020"
    store.seed_onboarded_user(phone, lang="eng")

    # Pick "Invite for an Event" from the menu
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("menu:event"))
    assert store.users[phone]["pending_flow"] == "event"
    assert store.users[phone]["current_step"] == "event_name"
    assert outbox.sent[-1][0] == "text"

    # Event name
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("Annual Onam Sadhya at Kannanthura Community Hall"))
    assert store.users[phone]["current_step"] == "event_when"
    assert "Onam" in store.users[phone]["session_data"]["name"]

    # Empty input is a no-op — flow stays on the datetime step.
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg(""))
    assert store.users[phone]["current_step"] == "event_when"

    # Date/time
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("September 7, 2026 at 12:30 PM"))
    assert store.users[phone]["current_step"] == "event_venue"
    assert "September 7" in store.users[phone]["session_data"]["when"]

    # Venue → triggers an asset-upload prompt with a skip button
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("Kannanthura Community Hall, near Beach Road"))
    assert store.users[phone]["current_step"] == "event_asset"
    assert outbox.sent[-1][0] == "buttons"
    button_ids = [b["id"] for b in outbox.sent[-1][1]["buttons"]]
    assert "event:skip_asset" in button_ids

    # Skip the asset upload
    user = store.get_user(phone)
    handlers.dispatch(phone, user, button_reply("event:skip_asset"))

    # Event invite persisted with no media id.
    assert len(store.event_invites) == 1
    invite = store.event_invites[0]
    assert invite["phone"] == phone
    assert "Onam" in invite["event_name"]
    assert "September 7" in invite["event_when"]
    assert "Community Hall" in invite["venue_address"]
    assert invite["invite_asset_media_id"] is None

    # Session cleared.
    assert store.users[phone]["current_step"] is None
    assert store.users[phone]["pending_flow"] is None
    assert store.users[phone]["session_data"] == {}

    # Success message sent.
    assert outbox.sent[-1][0] == "text"
    assert outbox.last_body("text")


def test_event_flow_with_image_attachment(harness):
    """Same flow, but with an image invitation card uploaded at the asset step."""
    store, outbox = harness
    import handlers

    phone = "919000000021"
    store.seed_onboarded_user(phone, lang="mal")

    # Skim through to the asset step.
    user = store.get_user(phone)
    handlers.dispatch(phone, user, list_reply("menu:event"))
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("Temple Festival Inauguration"))
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("October 12, 2026 at 6:00 PM"))
    user = store.get_user(phone)
    handlers.dispatch(phone, user, text_msg("Sree Padmanabha Temple grounds"))
    assert store.users[phone]["current_step"] == "event_asset"

    # Upload an image as the invitation asset.
    user = store.get_user(phone)
    handlers.dispatch(phone, user, _image_msg("wamid-fake-media-99", sender=phone))

    # Event row persisted with the media id captured.
    assert len(store.event_invites) == 1
    invite = store.event_invites[0]
    assert invite["invite_asset_media_id"] == "wamid-fake-media-99"
    assert "Temple Festival" in invite["event_name"]

    # Session cleared, success message sent.
    assert store.users[phone]["current_step"] is None
    assert store.users[phone]["pending_flow"] is None
    assert outbox.sent[-1][0] == "text"
