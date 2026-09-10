from app.services.decision_learning import DecisionLearningService


def test_learning_requires_organization():
    result = DecisionLearningService.build(None, [])
    assert result["success"] is False
    assert result["error"] == "organization_required"


def test_learning_builds_observational_rates(monkeypatch):
    projected = {
        "success": True,
        "items": [
            {"decision_id": "d1", "capability_id": "kemet.lead_scoring", "state": "approved"},
            {"decision_id": "d2", "capability_id": "kemet.lead_scoring", "state": "outcome_observed"},
            {"decision_id": "d3", "capability_id": "kemet.lead_scoring", "state": "reviewed"},
        ],
    }
    monkeypatch.setattr("app.services.decision_learning.DecisionLifecycleService.project", lambda *args, **kwargs: projected)
    result = DecisionLearningService.build(7, [{"action": "lead_scoring"}])
    assert result["success"] is True
    assert result["aggregate"]["decision_count"] == 3
    capability = result["capabilities"][0]
    assert capability["approval_rate"] == 0.6667
    assert capability["outcome_observed_rate"] == 1.0


def test_learning_enrich_is_recommendation_only(monkeypatch):
    monkeypatch.setattr(DecisionLearningService, "build", lambda *args, **kwargs: {
        "success": True,
        "capabilities": [{
            "capability_id": "kemet.lead_scoring",
            "decisions": 4,
            "approval_rate": 0.75,
            "execution_rate": 0.5,
            "outcome_observed_rate": 0.5,
        }],
    })
    result = DecisionLearningService.enrich(7, [{"action": "lead_scoring", "title": "Leads"}])
    signal = result["decisions"][0]["learning_signal"]
    assert signal["sample_size"] == 4
    assert signal["mode"] == "observational"
    assert "confidence_adjustment" in signal
    assert result["decisions"][0]["title"] == "Leads"


def test_learning_unknown_capability_fails_closed_in_signal():
    result = DecisionLearningService._capability({"action": "unknown_action"})
    assert result is None


def test_learning_governance_blocks_execution(monkeypatch):
    monkeypatch.setattr("app.services.decision_learning.DecisionLifecycleService.project", lambda *args, **kwargs: {"success": True, "items": []})
    result = DecisionLearningService.build(7, [])
    assert result["governance"]["read_only"] is True
    assert result["governance"]["auto_execute"] is False
    assert result["learning"]["causal_claim"] is False
