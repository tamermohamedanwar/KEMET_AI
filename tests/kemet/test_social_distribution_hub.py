from app.services.social_distribution_hub import SocialDistributionHub


def test_hub_has_single_publish_action_per_primary_channel():
    hub = SocialDistributionHub()
    assert set(hub.ACTIONS) == {
        "youtube", "tiktok", "instagram", "facebook", "telegram", "whatsapp", "linkedin"
    }
    assert hub.ACTIONS["youtube"] == "youtube_publish"
    assert hub.ACTIONS["tiktok"] == "tiktok_publish"
    assert hub.ACTIONS["facebook"] == "facebook_publish"


def test_hub_keeps_login_oauth_distinct_from_publishing_oauth():
    hub = SocialDistributionHub()
    assert hub.TARGETS["facebook"].connection_purpose == "content_publishing"
    assert hub.TARGETS["instagram"].connection_purpose == "content_publishing"
    assert hub.TARGETS["tiktok"].connection_purpose == "content_publishing"


def test_hub_plan_is_advisory_and_approval_gated(monkeypatch):
    hub = SocialDistributionHub()
    monkeypatch.setattr(
        "app.services.social_distribution_hub.social_channel_readiness_service.snapshot",
        lambda organization_id: {
            "channels": [
                {"id": "youtube", "configured": True, "connection": "not_connected"},
                {"id": "tiktok", "configured": False, "connection": "not_connected"},
            ]
        },
    )
    plan = hub.plan(1, asset_uri="content://episode-1", platforms=["youtube", "tiktok"])
    assert plan["status"] == "proposal_only"
    assert plan["approval"]["required"] is True
    assert plan["execution"]["runtime"] == "kemet_canonical_runtime"
    assert plan["execution"]["automatic"] is False
    assert plan["package_digest"]
