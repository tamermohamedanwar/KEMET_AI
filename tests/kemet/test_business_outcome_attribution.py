from app import create_app
from app.services.business_outcome_attribution import BusinessOutcomeAttribution


def test_attribution_is_observational_only():
    result = BusinessOutcomeAttribution.build(
        7, "kemet.business_insights", {"revenue": 100}, {"revenue": 125}
    )
    assert result["success"] is True
    assert result["observed"]["deltas"]["revenue"] == 25
    assert result["attribution"]["causal_claim"] is False
    assert result["attribution"]["roi_claim"] is False
    assert result["governance"]["read_only"] is True


def test_unknown_capability_fails_closed():
    result = BusinessOutcomeAttribution.build(7, "kemet.unknown", {}, {})
    assert result["success"] is False
    assert result["error"] == "capability_not_found"


def test_attribution_route_registered():
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/bos/capabilities/<path:capability_id>/attribution" in routes


def test_attribution_exposes_action_specific_measurement_contract():
    from app.services.business_outcome_attribution import BusinessOutcomeAttribution

    result = BusinessOutcomeAttribution.build(
        7,
        "kemet.ai_sales_qualification",
        {"leads_total": 10, "paid_amount": 100.0, "subscriptions_active": 2},
        {"leads_total": 12, "paid_amount": 125.0, "subscriptions_active": 3},
    )
    assert result["success"] is True
    measurement = result["measurement"]
    assert measurement["contract"]["domain"] == "sales"
    assert "leads_total" in measurement["relevant_deltas"]
    assert measurement["coverage"] == 1.0
    assert measurement["contract"]["interpretation"] == "observational_change_only"
