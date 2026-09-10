from app.core.analytics import ROIEngine


def test_roi_calculation():
    result = ROIEngine.calculate(
        revenue=100000,
        cost=25000,
        customers=20,
        leads=100,
        automated_tasks=500,
        manual_hours_saved=80,
    )

    assert result["success"] is True
    assert result["engine"] == "kemet_roi"
    assert result["metrics"]["net_value"] == 75000
    assert result["metrics"]["roi_percent"] == 300.0
    assert result["metrics"]["lead_to_customer_rate"] == 20.0


def test_roi_health():
    result = ROIEngine.calculate(
        revenue=100000,
        cost=25000,
    )

    assert result["decision"]["health"] == "excellent"
    assert result["decision"]["focus"] == "Scale high-performing operations"


def test_roi_report_is_governed():
    result = ROIEngine.calculate(
        revenue=50000,
        cost=20000,
    )

    report = ROIEngine.build_report(result)

    assert report["success"] is True
    assert report["requires_approval"] is True
    assert report["external_execution"] is False
