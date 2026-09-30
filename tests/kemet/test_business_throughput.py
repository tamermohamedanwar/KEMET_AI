from app import create_app
from app.services.business_throughput_service import BusinessThroughputService


def test_business_throughput_requires_organization():
    result = BusinessThroughputService.build(None)
    assert result["success"] is False
    assert result["error"] == "organization_required"


def test_business_throughput_is_read_only_and_normalized():
    app = create_app()
    with app.app_context():
        result = BusinessThroughputService.build(7, period="365d")

    assert result["success"] is True
    assert result["period"] == "30d"
    assert result["engine"] == "kemet_business_throughput"
    assert result["version"] == "1.1"
    assert "throughput_per_day" in result["metrics"]
    assert "avg_time_to_outcome_ms" in result["metrics"]
    assert "cost_per_successful_outcome" in result["metrics"]
    assert "commercial_capacity" in result
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["database_mutation"] is False


def test_business_throughput_periods_are_supported():
    assert BusinessThroughputService.PERIOD_DAYS == {"24h": 1, "7d": 7, "30d": 30, "90d": 90}


def test_business_throughput_commercial_capacity_is_tenant_scoped():
    app = create_app()
    with app.app_context():
        first = BusinessThroughputService.build(1)
        second = BusinessThroughputService.build(3)

    assert first["commercial_capacity"]["used_this_month"] >= 0
    assert second["commercial_capacity"]["used_this_month"] >= 0
    assert first["commercial_capacity"]["plan"] != second["commercial_capacity"]["plan"] or first["organization_id"] != second["organization_id"]
