from app.services.tiktok_discovery_service import TikTokDiscoveryQuery, tiktok_discovery_service


def test_tiktok_discovery_plan_is_read_only():
    result = tiktok_discovery_service.plan(TikTokDiscoveryQuery(1, "تسويق إلكتروني"))
    assert result["success"] is True
    assert result["plan"]["read_only"] is True
    assert result["plan"]["execution_authority"] is False
    assert result["plan"]["credentials_exposed"] is False


def test_tiktok_discovery_rank_uses_public_signals():
    result = tiktok_discovery_service.rank(TikTokDiscoveryQuery(1, "marketing"), [{"id": 10, "username": "demo", "view_count": 10000, "like_count": 1000, "comment_count": 100, "share_count": 50, "hashtag_names": ["marketing"]}])
    assert result["success"] is True
    assert result["results"][0]["video_id"] == "10"
    assert result["results"][0]["engagement_rate"] > 0
    assert result["read_only"] is True


def test_tiktok_discovery_fails_closed():
    result = tiktok_discovery_service.plan(TikTokDiscoveryQuery(0, "marketing"))
    assert result["status"] == "blocked"
