from app.services.outcome_priority import OutcomePriorityService


def test_priority_requires_organization():
    result = OutcomePriorityService.rank(None, [])
    assert result["error"] == "organization_required"


def test_priority_ranks_by_advisory_score(monkeypatch):
    def fake_build(org, capability, period):
        return {
            "success": True,
            "observed_impact": [{"metric": "paid_amount", "delta": 25, "direction": "positive"}],
            "confidence": {"score": 0.9, "level": "high"},
        }
    monkeypatch.setattr("app.services.outcome_priority.outcome_intelligence.build", fake_build)
    decisions = [
        {"action": "revenue_opportunity", "priority": "high", "title": "Revenue"},
        {"action": "lead_scoring", "priority": "low", "title": "Leads"},
    ]
    result = OutcomePriorityService.rank(7, decisions)
    assert result["success"] is True
    assert result["items"][0]["title"] == "Revenue"
    assert result["items"][0]["outcome_priority_score"] > 0


def test_priority_skips_unknown_capability():
    result = OutcomePriorityService.rank(7, [{"action": "unknown_action", "priority": "critical"}])
    assert result["success"] is True
    assert result["items"] == []
    assert result["governance"]["causal_claim"] is False
    assert result["governance"]["roi_claim"] is False


def test_priority_is_read_only(monkeypatch):
    def fake_build(org, capability, period):
        return {"success": True, "observed_impact": [], "confidence": {"score": 0.5, "level": "low"}}
    monkeypatch.setattr("app.services.outcome_priority.outcome_intelligence.build", fake_build)
    result = OutcomePriorityService.rank(7, [{"action": "lead_scoring"}])
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["database_mutation"] is False


def test_priority_empty_decisions_is_safe():
    result = OutcomePriorityService.rank(7, [])
    assert result["success"] is True
    assert result["items"] == []
    assert result["count"] == 0
