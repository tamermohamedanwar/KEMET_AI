from app import create_app
from app.services.business_outcome_service import BusinessOutcomeService


def test_business_outcome_requires_organization():
    result = BusinessOutcomeService.build(None)
    assert result["success"] is False
    assert result["error"] == "organization_required"


def test_business_outcome_normalizes_unknown_period():
    app = create_app()
    with app.app_context():
        result = BusinessOutcomeService.build(7, period="365d")
    assert result["success"] is True
    assert result["period"] == "30d"


def test_business_outcome_is_advisory_and_structured():
    app = create_app()
    with app.app_context():
        result = BusinessOutcomeService.build(7, period="30d")

    assert result["success"] is True
    assert result["engine"] == "kemet_outcome"
    assert result["period"] == "30d"
    assert "health_score" in result
    assert "automation" in result
    assert "roi" in result
    assert "next_best_actions" in result
    assert result["governance"]["mode"] == "advisory"
    assert result["governance"]["requires_approval"] is True
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["database_mutation"] is False


def test_execution_outcome_requires_complete_execution_identity():
    from app.services.business_outcome_service import BusinessOutcomeService

    baseline = {"success": True, "metrics": {"paid_amount": 100}, "execution_identity": {"organization_id": 7}}
    result = BusinessOutcomeService.build_execution_outcome(7, "kemet.business_insights", baseline, execution_identity=None)
    assert result["success"] is False
    assert result["error"] == "execution_identity_required"


def test_execution_outcome_binds_baseline_to_exact_execution_identity(monkeypatch):
    from app.services.business_outcome_service import BusinessOutcomeService

    identity = {"organization_id": 7, "workflow_id": 11, "execution_id": 22, "execution_key": "exec-22", "idempotency_key": "idem-22"}
    baseline = {"success": True, "period": "30d", "metrics": {"paid_amount": 100}, "execution_identity": identity}
    monkeypatch.setattr(BusinessOutcomeService, "capture_snapshot", classmethod(lambda cls, organization_id, period="30d", execution_identity=None: {"success": True, "period": period, "captured_at": "now", "metrics": {"paid_amount": 125}, "execution_identity": execution_identity}))
    result = BusinessOutcomeService.build_execution_outcome(7, "kemet.business_insights", baseline, execution_identity=identity)
    assert result["success"] is True
    assert result["execution_identity"] == identity
    assert result["baseline"]["execution_identity"] == identity
    assert result["attribution"]["causal_claim"] is False
    assert result["attribution"]["roi_claim"] is False


def test_execution_outcome_rejects_substituted_or_cross_tenant_identity(monkeypatch):
    from app.services.business_outcome_service import BusinessOutcomeService

    identity = {"organization_id": 7, "workflow_id": 11, "execution_id": 22, "execution_key": "exec-22", "idempotency_key": "idem-22"}
    baseline = {"success": True, "period": "30d", "metrics": {"paid_amount": 100}, "execution_identity": identity}
    other = dict(identity, execution_id=23, execution_key="exec-23", idempotency_key="idem-23")
    result = BusinessOutcomeService.build_execution_outcome(7, "kemet.business_insights", baseline, execution_identity=other)
    assert result["success"] is False
    assert result["error"] == "baseline_execution_identity_mismatch"
    cross_tenant = dict(identity, organization_id=8)
    result = BusinessOutcomeService.build_execution_outcome(7, "kemet.business_insights", baseline, execution_identity=cross_tenant)
    assert result["success"] is False
    assert result["error"] == "execution_identity_tenant_mismatch"
