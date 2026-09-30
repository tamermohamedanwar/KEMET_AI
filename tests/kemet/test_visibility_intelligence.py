from app.services.kemet_visibility_intelligence_service import kemet_visibility_intelligence_service


def test_visibility_loop_is_revenue_connected():
    snapshot = kemet_visibility_intelligence_service.snapshot(7)
    assert snapshot["loop"] == [
        "content", "distribution", "visibility", "audience",
        "qualified_views", "revenue", "learning",
    ]


def test_visibility_never_fabricates_measurements():
    snapshot = kemet_visibility_intelligence_service.snapshot(7)
    assert snapshot["totals"]["brand_mentions"] is None
    assert snapshot["totals"]["visibility_rate"] is None
    assert all(item["source_verified"] is False for item in snapshot["surfaces"])


def test_visibility_public_api_discovery_is_non_executing():
    discovery = kemet_visibility_intelligence_service.public_api_discovery(7)
    assert discovery["purpose"] == "discovery_only"
    assert discovery["selection_policy"]["no_automatic_connection"] is True
