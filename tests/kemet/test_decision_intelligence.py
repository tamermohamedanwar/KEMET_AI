from app.services.decision_intelligence import DecisionIntelligenceService


def test_intelligence_requires_organization():
    result = DecisionIntelligenceService.build(None, [])
    assert result["error"] == "organization_required"


def test_score_returns_unified_advisory_score():
    result = DecisionIntelligenceService.score(
        {"priority": "high", "confidence": 0.8, "impact": 50},
        {"learning_factor": 0.75, "confidence_adjustment": 0.02},
    )
    assert 0 <= result["score"] <= 1
    assert result["level"] in {"critical", "high", "medium", "low"}


def test_intelligence_is_read_only(monkeypatch):
    monkeypatch.setattr(
        "app.services.decision_intelligence.decision_learning.enrich",
        lambda *args, **kwargs: {"success": True, "decisions": [{"action": "lead_scoring", "learning_signal": {"learning_factor": 0.7, "confidence_adjustment": 0.01}}]},
    )
    result = DecisionIntelligenceService.build(7, [{"action": "lead_scoring"}])
    assert result["success"] is True
    assert result["governance"]["read_only"] is True
    assert result["governance"]["auto_execute"] is False
    assert result["governance"]["human_approval_required"] is True
