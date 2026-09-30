from app.services.social_connection_hub import social_connection_hub


def test_social_hub_unifies_major_channels_without_claiming_one_token():
    snapshot = social_connection_hub.snapshot(1)
    ids = {x["channel_id"] for x in snapshot["channels"]}
    assert {"youtube", "tiktok", "instagram", "facebook", "telegram", "whatsapp"} <= ids
    assert {"snapchat", "pinterest", "linkedin", "x", "threads"} <= ids
    assert snapshot["connect_all"]["available"] is True
    assert snapshot["connect_all"]["single_token"] is False
    assert snapshot["governance"]["no_credentials_exposed"] is True
