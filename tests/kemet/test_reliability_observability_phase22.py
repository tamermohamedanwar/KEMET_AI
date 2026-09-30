from app.core.reliability import (
    ReliabilityObservation,
    classify_exception,
    normalize_error_category,
    reliability_snapshot,
)
from app.services.reliability_slo import reliability_slo


def test_error_taxonomy_is_closed_and_unknown_fails_closed():
    assert normalize_error_category("timeout") == "timeout"
    assert normalize_error_category("unknown_category") == "internal_error"
    assert classify_exception(TimeoutError("x")) == "timeout"


def test_reliability_snapshot_is_measurement_only():
    result = reliability_snapshot.summarize([
        ReliabilityObservation("a", "success", 10),
        ReliabilityObservation("b", "failure", 20, "database_error", 2),
    ])
    assert result["success_rate"] == 0.5
    assert result["p95_duration_ms"] == 10
    assert result["retries"] == 2
    assert result["measurement_only"] is True
    assert result["execution_authority"] is False


def test_slo_catalog_remains_non_authorizing():
    catalog = reliability_slo.catalog()
    assert catalog["measurement_only"] is True
    assert catalog["execution_authority"] is False
    assert catalog["policy_separate"] is True


def test_observability_health_report_is_non_production_claiming():
    from ops.observability_health import build_report

    report = build_report()
    assert report["schema"] == "kemet.observability_health.v1"
    assert report["secret_exposed"] is False
    assert report["production_claim"] is False
    assert report["checks"]["database_telemetry"] is True
    assert report["checks"]["reliability_catalog"] is True
    assert isinstance(report["evidence_digest"], str)
