import uuid

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.execution_evidence import execution_evidence


def test_execution_evidence_history_is_durable_and_idempotent():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Evidence {uid}", slug=f"evidence-{uid}")
        db.session.add(org)
        db.session.commit()
        first = execution_evidence.record(
            organization_id=org.id, execution_key=f"exec-{uid}",
            stage="ledger.started", status="started",
            evidence_key=f"exec-{uid}:ledger.started", plan_hash="p1",
            trace_id="trace-1", correlation_id="corr-1",
            receipt={"ledger_id": 7},
        )
        second = execution_evidence.record(
            organization_id=org.id, execution_key=f"exec-{uid}",
            stage="ledger.started", status="started",
            evidence_key=f"exec-{uid}:ledger.started", plan_hash="changed",
        )
        history = execution_evidence.history(
            organization_id=org.id, execution_key=f"exec-{uid}"
        )
        assert first["id"] == second["id"]
        assert len(history) == 1
        assert history[0]["trace_id"] == "trace-1"
        assert history[0]["receipt"]["ledger_id"] == 7


def test_execution_evidence_is_tenant_scoped():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        first = Organization(name=f"A {uid}", slug=f"ev-a-{uid}")
        second = Organization(name=f"B {uid}", slug=f"ev-b-{uid}")
        db.session.add_all([first, second])
        db.session.commit()
        execution_evidence.record(
            organization_id=first.id, execution_key="same",
            stage="runtime.finished", status="completed",
            evidence_key="same:runtime.finished",
        )
        execution_evidence.record(
            organization_id=second.id, execution_key="same",
            stage="runtime.finished", status="completed",
            evidence_key="same:runtime.finished",
        )
        assert len(execution_evidence.history(organization_id=first.id, execution_key="same")) == 1
        assert len(execution_evidence.history(organization_id=second.id, execution_key="same")) == 1
