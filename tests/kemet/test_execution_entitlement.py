from datetime import datetime

from app import create_app, db
from app.models.automation_execution_ledger import AutomationExecutionLedger
from app.services.execution_entitlement_service import ExecutionEntitlementService


def test_execution_entitlement_requires_organization():
    result = ExecutionEntitlementService.check(None)
    assert result["allowed"] is False
    assert result["reason"] == "organization_required"


def test_execution_entitlement_blocks_free_plan():
    app = create_app()
    with app.app_context():
        result = ExecutionEntitlementService.check(2, "quota-test-free")
    assert result["allowed"] is False
    assert result["reason"] == "automation_feature_not_available"


def test_execution_entitlement_is_tenant_scoped():
    app = create_app()
    with app.app_context():
        row = AutomationExecutionLedger(
            organization_id=1, execution_key="tenant-scope-test",
            plan_hash="test", status="started", created_at=datetime.utcnow(),
        )
        db.session.add(row)
        db.session.commit()
        result = ExecutionEntitlementService.check(3, "tenant-scope-test")
    assert result["allowed"] is True
    assert result["used"] == 0
