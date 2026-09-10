from app import create_app
from app.services.decision_lifecycle import DecisionLifecycleService


def test_lifecycle_requires_organization():
    result = DecisionLifecycleService.project(None, [])
    assert result["success"] is False
    assert result["error"] == "organization_required"


def test_lifecycle_detected_when_unranked(monkeypatch):
    app = create_app()
    with app.app_context():
        monkeypatch.setattr(DecisionLifecycleService, "_approval_records", lambda *args: [])
        monkeypatch.setattr(DecisionLifecycleService, "_execution_records", lambda *args: [])
        result = DecisionLifecycleService.build(7, {
            "decision_id": "d-1",
            "action": "business_insights",
        })
    assert result["success"] is True
    assert result["state"] == "detected"


def test_lifecycle_ranked_when_priority_exists(monkeypatch):
    app = create_app()
    with app.app_context():
        monkeypatch.setattr(DecisionLifecycleService, "_approval_records", lambda *args: [])
        monkeypatch.setattr(DecisionLifecycleService, "_execution_records", lambda *args: [])
        result = DecisionLifecycleService.build(7, {
            "decision_id": "d-2",
            "action": "business_insights",
            "outcome_priority_score": 72.0,
        })
    assert result["state"] == "ranked"


def test_lifecycle_invalid_decision_fails_closed():
    app = create_app()
    with app.app_context():
        result = DecisionLifecycleService.build(7, {})
    assert result["success"] is False
    assert result["error"] == "decision_id_required"


def test_lifecycle_governance_is_read_only(monkeypatch):
    app = create_app()
    with app.app_context():
        monkeypatch.setattr(DecisionLifecycleService, "_approval_records", lambda *args: [])
        monkeypatch.setattr(DecisionLifecycleService, "_execution_records", lambda *args: [])
        result = DecisionLifecycleService.build(7, {
            "decision_id": "d-3",
            "action": "business_insights",
        })
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["database_mutation"] is False
    assert result["governance"]["causal_claim"] is False
    assert result["governance"]["roi_claim"] is False


def test_lifecycle_projection_is_organization_scoped(monkeypatch):
    app = create_app()
    with app.app_context():
        monkeypatch.setattr(DecisionLifecycleService, "build", lambda org, decision, period: {
            "success": True, "organization_id": org, "decision_id": decision["decision_id"]
        })
        result = DecisionLifecycleService.project(42, [{"decision_id": "d-4"}])
    assert result["success"] is True
    assert result["organization_id"] == 42
    assert result["items"][0]["organization_id"] == 42

def test_lifecycle_accountability_fields_are_present(monkeypatch):
    app = create_app()
    with app.app_context():
        monkeypatch.setattr(DecisionLifecycleService, "_approval_records", lambda *args: [])
        monkeypatch.setattr(DecisionLifecycleService, "_execution_records", lambda *args: [])
        result = DecisionLifecycleService.build(7, {
            "decision_id": "d-accountability",
            "action": "business_insights",
        })
    assert result["approval"]["requested_by"] is None
    assert result["approval"]["decided_by"] is None
    assert "history" in result
    assert result["governance"]["read_only"] is True

