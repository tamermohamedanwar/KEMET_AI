from app import create_app
from app.services.outcome_intelligence import OutcomeIntelligenceService


def test_missing_org_fails_closed():
    result = OutcomeIntelligenceService.build(None, "kemet.business_insights")
    assert result["error"] == "organization_required"


def test_unknown_capability_fails_closed():
    result = OutcomeIntelligenceService.build(7, "kemet.unknown")
    assert result["error"] == "capability_not_found"


def test_outcome_intelligence_is_non_causal(monkeypatch):
    def fake_snapshot(org, period):
        return {"paid_amount": 100.0 if period == "90d" else 125.0, "leads_total": 10, "tickets_open": 2}
    monkeypatch.setattr(OutcomeIntelligenceService, "_snapshot", staticmethod(fake_snapshot))
    result = OutcomeIntelligenceService.build(7, "kemet.business_insights", "30d")
    assert result["success"] is True
    assert result["attribution"]["causal_claim"] is False
    assert result["attribution"]["roi_claim"] is False
    assert result["governance"]["read_only"] is True
    assert result["confidence"]["score"] > 0


def test_outcome_intelligence_route_registered():
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/bos/outcome-intelligence" in routes
