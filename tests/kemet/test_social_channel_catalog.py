from app.services.social_channel_catalog import social_channel_catalog
from app.services.social_channel_readiness_service import social_channel_readiness_service


def test_catalog_covers_major_distribution_channels():
    ids = {x["channel_id"] for x in social_channel_catalog.snapshot(1)["channels"]}
    assert {"youtube", "tiktok", "instagram", "facebook", "snapchat", "telegram", "whatsapp"} <= ids
    assert {"pinterest", "linkedin", "x", "threads"} <= ids


def test_catalogued_channels_do_not_claim_connection():
    snapshot = social_channel_readiness_service.snapshot(1)
    rows = {x["channel_id"]: x for x in snapshot["channels"]}
    for channel in ("snapchat", "pinterest", "linkedin", "x", "threads"):
        assert rows[channel]["connection"] == "not_connected"
        assert rows[channel]["credentials_exposed"] is False
        assert rows[channel]["publish_state"] == "approval_required"
