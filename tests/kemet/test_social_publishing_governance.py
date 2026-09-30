from app.core.execution.governed_executor import governed_execution_service
from app.services.social_channel_readiness_service import social_channel_readiness_service


def test_all_social_publish_actions_are_approval_gated():
    for action in (
        "youtube_publish", "tiktok_publish", "instagram_publish",
        "facebook_publish", "telegram_publish", "whatsapp_publish",
    ):
        assert governed_execution_service._policy(action) == "approval_required"


def test_readiness_contains_distinct_publishing_authority():
    snapshot = social_channel_readiness_service.snapshot(1)
    channels = {row["id"]: row for row in snapshot["channels"]}
    assert channels["facebook"]["publishing_authority"] == "facebook_page_publishing_oauth"
    assert channels["instagram"]["publishing_authority"] == "instagram_publishing_oauth"
    assert channels["tiktok"]["publishing_authority"] == "video.publish_or_video.upload"
    assert snapshot["governance"]["login_oauth_is_not_publishing_authority"] is True


def test_readiness_never_claims_connection_from_configuration():
    snapshot = social_channel_readiness_service.snapshot(1)
    assert all(row["connection"] == "not_connected" for row in snapshot["channels"])
    assert all(row["credentials_exposed"] is False for row in snapshot["channels"])
