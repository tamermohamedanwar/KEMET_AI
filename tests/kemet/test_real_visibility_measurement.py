import pytest

from app.services.real_visibility_measurement_service import (
    STATUS_NOT_CONNECTED,
    RealVisibilityMeasurementService,
    VisibilityMeasurement,
)


def test_real_visibility_contract_is_explicit_and_non_fabricating():
    snapshot = RealVisibilityMeasurementService.empty_snapshot(7)
    assert snapshot["status"] == STATUS_NOT_CONNECTED
    assert snapshot["measurements"] == []
    assert snapshot["governance"]["no_fabricated_metrics"] is True
    assert "evidence" in snapshot["contract"]


def test_verified_measurement_requires_evidence_and_signal():
    measurement = VisibilityMeasurement(
        source="google",
        market="egypt",
        language="ar",
        query="Kemet AI BOS",
        timestamp=RealVisibilityMeasurementService.new_timestamp(),
        visibility_signal=1.0,
        mention=True,
        position_signal=1.0,
        competitor_signal=0.0,
        evidence={"source": "official_google_api", "reference": "report-1"},
        verified=True,
    )
    normalized = RealVisibilityMeasurementService.normalize(measurement)
    assert normalized["verified"] is True
    assert normalized["evidence"]["source"] == "official_google_api"


def test_verified_measurement_without_evidence_is_rejected():
    measurement = VisibilityMeasurement(
        source="chatgpt",
        market="global",
        language="en",
        query="Kemet",
        timestamp=RealVisibilityMeasurementService.new_timestamp(),
        visibility_signal=1.0,
        mention=True,
        position_signal=None,
        competitor_signal=None,
        evidence=None,
        verified=True,
    )
    with pytest.raises(ValueError, match="verified_visibility_requires_evidence"):
        RealVisibilityMeasurementService.normalize(measurement)


def test_unknown_source_is_rejected():
    measurement = VisibilityMeasurement(
        source="unknown",
        market="global",
        language="en",
        query="Kemet",
        timestamp=RealVisibilityMeasurementService.new_timestamp(),
        visibility_signal=None,
        mention=None,
        position_signal=None,
        competitor_signal=None,
        evidence=None,
        verified=False,
    )
    with pytest.raises(ValueError, match="unsupported_visibility_source"):
        RealVisibilityMeasurementService.normalize(measurement)
