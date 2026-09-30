from app.services.social_channel_readiness_service import social_channel_readiness_service


def test_all_major_social_channels_are_registered():
    snapshot = social_channel_readiness_service.snapshot(1)
    ids = {row["channel_id"] for row in snapshot["channels"]}
    assert {"youtube", "tiktok", "instagram", "facebook", "telegram", "whatsapp"} <= ids
    assert {"snapchat", "pinterest", "linkedin", "x", "threads"} <= ids


def test_readiness_never_claims_connection_from_configuration():
    snapshot = social_channel_readiness_service.snapshot(1)
    assert all(row["connection"] == "not_connected" for row in snapshot["channels"])
    assert all(row["credentials_exposed"] is False for row in snapshot["channels"])
