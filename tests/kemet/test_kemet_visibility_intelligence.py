from app.services.kemet_visibility_intelligence_service import kemet_visibility_intelligence_service


def test_visibility_intelligence_covers_search_and_ai_surfaces():
    snapshot = kemet_visibility_intelligence_service.snapshot(7)
    assert [surface["surface_id"] for surface in snapshot["surfaces"]] == [
        "google_search", "chatgpt", "gemini",
    ]
    assert snapshot["brand"] == "Kemet"


def test_visibility_metrics_are_not_fabricated():
    snapshot = kemet_visibility_intelligence_service.snapshot(7)
    assert snapshot["totals"]["brand_mentions"] is None
    assert snapshot["totals"]["visibility_rate"] is None
    assert all(surface["source_verified"] is False for surface in snapshot["surfaces"])


def test_visibility_is_part_of_revenue_loop_without_execution_authority():
    snapshot = kemet_visibility_intelligence_service.snapshot(7)
    assert snapshot["loop"] == [
        "content", "distribution", "visibility", "audience",
        "qualified_views", "revenue", "learning",
    ]
    assert snapshot["governance"]["read_only"] is True
    assert snapshot["governance"]["no_auto_publish"] is True
    assert snapshot["governance"]["no_external_execution"] is True
