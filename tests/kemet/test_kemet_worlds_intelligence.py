from app.services.kemet_worlds_intelligence_service import kemet_worlds_intelligence_service


def test_kemet_worlds_is_parent_to_mendes_and_analytics_are_read_only():
    snapshot = kemet_worlds_intelligence_service.snapshot(7)
    assert snapshot["world_id"] == "kemet-worlds"
    assert "Mendes World" in snapshot["child_worlds"]
    assert snapshot["analysis"]["primary_kpi"] == "revenue_per_1000_qualified_views"
    assert snapshot["governance"]["read_only"] is True
    assert snapshot["governance"]["no_auto_publish"] is True


def test_unverified_world_metrics_are_not_fabricated():
    snapshot = kemet_worlds_intelligence_service.snapshot(7)
    assert snapshot["totals"]["views"] is None
    assert snapshot["totals"]["revenue"] is None
    assert all(channel["revenue"] is None for channel in snapshot["channels"])


def test_world_funnel_preserves_revenue_first_sequence():
    funnel = kemet_worlds_intelligence_service.snapshot(7)["analysis"]["funnel"]
    assert funnel == [
        "content", "publication", "views", "retention",
        "qualified_views", "monetization", "revenue", "learning",
    ]


def test_verified_youtube_measurement_flows_into_worlds():
    evidence = {
        "verified": True,
        "source": "youtube_analytics_api",
        "evidence_digest": "digest-1",
        "evidence": {
            "headers": [
                {"name": "views"},
                {"name": "estimatedMinutesWatched"},
                {"name": "averageViewPercentage"},
                {"name": "estimatedRevenue"},
            ],
            "rows": [[1000, 250, 0.5, 20]],
        },
    }
    snapshot = kemet_worlds_intelligence_service.snapshot(7, youtube_evidence=evidence)
    assert snapshot["status"] == "measured"
    assert snapshot["totals"]["views"] == 1000
    assert snapshot["totals"]["revenue"] == 20
    assert snapshot["totals"]["qualified_views"] is None
    assert snapshot["evidence"]["digest"] == "digest-1"
