from app.services.google_visibility_measurement_service import (
    GoogleVisibilityMeasurementService,
)


def test_google_measurement_preserves_common_contract():
    result = GoogleVisibilityMeasurementService.build_measurement(
        organization_id=7,
        market="eg",
        language="ar",
        query="Kemet AI",
        row={"clicks": 12, "impressions": 100, "position": 4.5, "verified_source": True},
    )
    assert result["source"] == "google_search_console"
    assert result["market"] == "eg"
    assert result["language"] == "ar"
    assert result["query"] == "Kemet AI"
    assert result["position_signal"] == 4.5
    assert result["verified"] is True
    assert result["evidence"]["source_contract"] == "Google Search Console API"


def test_google_measurement_does_not_invent_missing_signals():
    result = GoogleVisibilityMeasurementService.build_measurement(
        organization_id=7,
        market="global",
        language="en",
        query="Kemet",
        row={},
    )
    assert result["position_signal"] is None
    assert result["mention"] is None
    assert result["competitor_signal"] is None
    assert result["verified"] is False


def test_google_measurement_is_evidence_ready_only_when_source_verified():
    verified = GoogleVisibilityMeasurementService.build_measurement(
        organization_id=7,
        market="eg",
        language="ar",
        query="Kemet",
        row={"verified_source": True},
    )
    unverified = GoogleVisibilityMeasurementService.build_measurement(
        organization_id=7,
        market="eg",
        language="ar",
        query="Kemet",
        row={"verified_source": False},
    )
    assert verified["evidence"]["source_verified"] is True
    assert unverified["evidence"]["source_verified"] is False


def test_youtube_evidence_requires_verified_google_source():
    from app.services.google_visibility_measurement_service import build_youtube_evidence
    result = build_youtube_evidence(7, {"source": "youtube_analytics_api", "verified_source": True, "rows": [[1]], "headers": ["views"]})
    assert result["verified"] is True
    assert result["evidence"]["source_verified"] is True
