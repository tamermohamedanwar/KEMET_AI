from app.services.revenue_collection_service import RevenueCollectionService


def test_revenue_center_catalog_is_kemet_wide_and_read_only():
    snapshot = RevenueCollectionService.snapshot(42)
    ids = {row["channel_id"] for row in snapshot["channels"]}
    assert {"youtube", "tiktok", "instagram", "facebook", "affiliate", "marketplace"} <= ids
    assert snapshot["organization_id"] == 42
    assert snapshot["governance"]["read_only"] is True
    assert snapshot["governance"]["no_payout_execution"] is True


def test_revenue_center_never_fabricates_financial_values():
    snapshot = RevenueCollectionService.snapshot(42)
    assert snapshot["total_balance"] is None
    assert snapshot["pending_payout"] is None
    assert snapshot["verified_revenue"] is None
    assert all(row["balance"] is None for row in snapshot["channels"])
    assert all(row["payout_destination"] == "not_configured" for row in snapshot["channels"])


def test_verified_youtube_revenue_is_measurement_not_balance():
    evidence = {
        "verified": True,
        "source": "youtube_analytics_api",
        "evidence_digest": "abc123",
        "evidence": {
            "timestamp": "2026-09-15T00:00:00+00:00",
            "headers": [{"name": "estimatedRevenue"}],
            "rows": [[12.5]],
        },
    }
    snapshot = RevenueCollectionService.snapshot(42, evidence)
    youtube = next(x for x in snapshot["channels"] if x["channel_id"] == "youtube")
    assert snapshot["verified_revenue"] == 12.5
    assert snapshot["total_balance"] is None
    assert youtube["connection_status"] == "connected"
    assert youtube["balance"] is None
    assert youtube["evidence_digest"] == "abc123"
