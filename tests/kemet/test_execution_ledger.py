import uuid

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.execution_ledger import execution_ledger


def test_execution_ledger_is_durable_and_idempotent():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Ledger {uid}", slug=f"ledger-{uid}")
        db.session.add(org)
        db.session.commit()
        key = f"exec-{uid}"
        first = execution_ledger.begin(
            organization_id=org.id, execution_key=key,
            plan_hash="plan-hash", worker_id="worker-1",
        )
        second = execution_ledger.begin(
            organization_id=org.id, execution_key=key,
            plan_hash="plan-hash", worker_id="worker-2",
        )
        assert first["created"] is True
        assert second["created"] is False
        assert second["record"]["worker_id"] == "worker-1"
        assert execution_ledger.finish(
            organization_id=org.id, execution_key=key,
            status="completed", receipt={"executed": True},
        ) is True
        saved = execution_ledger.get(organization_id=org.id, execution_key=key)
        assert saved["status"] == "completed"
        assert saved["receipt"]["executed"] is True


def test_execution_ledger_rejects_cross_tenant_reuse():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        first = Organization(name=f"A {uid}", slug=f"a-{uid}")
        second = Organization(name=f"B {uid}", slug=f"b-{uid}")
        db.session.add_all([first, second])
        db.session.commit()
        key = f"same-{uid}"
        execution_ledger.begin(organization_id=first.id, execution_key=key, plan_hash="p")
        other = execution_ledger.begin(organization_id=second.id, execution_key=key, plan_hash="p")
        assert other["created"] is True


# End of ledger tests.
