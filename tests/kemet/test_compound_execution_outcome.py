import json
import uuid

import pytest

from wsgi import application
from app import db
from app.models.organization import Organization
from app.models.automation_execution_ledger import AutomationExecutionLedger
from app.models.execution_evidence import ExecutionEvidence
from app.core.execution.authorization import ExecutionAuthorizationService, execution_authorization
from app.core.execution_ledger import execution_ledger
from app.core.execution_evidence import execution_evidence
from app.core.external_task_lifecycle import external_task_lifecycle
from app.core.federation.manus_adapter import ManusAdapter
from app.core.federation.outcome_control import OutcomeControlService
from app.core.federation.outcome_lifecycle import OutcomeLifecycleError, outcome_lifecycle
from app.core.federation.specialist_contracts import SpecialistRequest


def _org():
    uid = uuid.uuid4().hex
    row = Organization(name=f"Compound {uid}", slug=f"compound-{uid}")
    db.session.add(row)
    db.session.commit()
    return row


def test_execute_reconcile_receipt_evidence_outcome_chain(monkeypatch):
    monkeypatch.setenv("MANUS_API_KEY", "test-key")
    monkeypatch.setenv("KEMET_EXECUTION_SECRET", "compound-secret")
    execution_authorization.secret = "compound-secret"

    class Response:
        ok = True

        def json(self):
            return {"ok": True, "task_id": external_task_id, "request_id": request_id}

    with application.app_context():
        db.create_all()
        org = _org()
        execution_key = f"exec-compound-{uuid.uuid4().hex}"
        external_task_id = f"manus-{execution_key}"
        request_id = f"req-{execution_key}"
        decision_hash = f"decision-hash-{execution_key}"
        plan = {
            "plan_id": f"plan-{execution_key}",
            "plan_hash": f"hash-{execution_key}",
            "organization_id": org.id,
            "action": "manus.task.create",
            "execution_key": execution_key,
            "decision_hash": decision_hash,
        }
        authorization = ExecutionAuthorizationService().create_authorization(plan, approver_id=42)
        monkeypatch.setattr("app.core.federation.manus_adapter.governed_request", lambda *a, **k: Response())
        result = ManusAdapter().submit(
            SpecialistRequest(org.id, "compound-task", "research"), plan=plan, authorization=authorization
        )
        assert result.status == "submitted"
        assert result.external_task_id == external_task_id
        execution_ledger.begin(organization_id=org.id, execution_key=execution_key,
                               plan_hash=plan["plan_hash"], decision_hash=decision_hash)
        execution_ledger.finish(
            organization_id=org.id, execution_key=execution_key, status="submitted",
            receipt={"provider_id": "manus", "action": plan["action"],
                     "external_task_id": external_task_id, "request_id": request_id, "status": "submitted"},
        )
        execution_evidence.record(
            organization_id=org.id, execution_key=execution_key,
            stage="specialist.execution_submitted", status="submitted",
            evidence_key=f"{execution_key}:specialist.execution_submitted",
            plan_hash=plan["plan_hash"],
            receipt={"provider_id": "manus", "external_task_id": external_task_id, "request_id": request_id},
        )
        ledger = execution_ledger.get(organization_id=org.id, execution_key=execution_key)
        assert ledger["status"] == "submitted"
        assert ledger["receipt"]["external_task_id"] == external_task_id

        external_task_lifecycle.mark_ambiguous(
            organization_id=org.id, execution_key=execution_key, reason="timeout_after_submit"
        )
        reconciled = external_task_lifecycle.reconcile_provider_completion(
            organization_id=org.id, execution_key=execution_key, provider_id="manus",
            external_task_id=external_task_id, plan_hash=plan["plan_hash"], request_id=request_id,
            result={"summary": "compound completion", "value": 150},
        )
        assert reconciled["status"] == "completed"
        ledger = execution_ledger.get(organization_id=org.id, execution_key=execution_key)
        assert ledger["status"] == "completed"
        assert ledger["receipt"]["provider_completion"]["status"] == "completed"
        evidence = execution_evidence.history(organization_id=org.id, execution_key=execution_key)
        assert any(item.get("stage") == "external_task.provider_reconciled" for item in evidence)
        contract = OutcomeControlService().contract(
            decision={
                "decision_id": f"decision-{execution_key}",
                "task_id": "compound-task",
                "organization_id": org.id,
                "digest": "c" * 64,
                "decision_hash": decision_hash,
            },
            expected_metrics=[{"metric": "revenue", "baseline": 100, "target": 150}],
        )
        ctx = {"window": "30d", "as_of": "2026-09-12"}
        bound = outcome_lifecycle.bind_contract(
            contract=contract, organization_id=org.id, execution_key=execution_key,
            provider_id="manus", evidence_context_hash="compound-evidence", measurement_context=ctx,
        )
        assert bound["execution_receipt_digest"] == execution_ledger.receipt_digest(ledger["receipt"])
        ledger_row = db.session.get(AutomationExecutionLedger, ledger["id"])
        original_receipt = ledger_row.receipt_json
        ledger_row.receipt_json = json.dumps({"provider_id": "grok", "external_task_id": "wrong",
                                              "execution_identity": {"decision_hash": decision_hash}})
        db.session.commit()
        with pytest.raises(OutcomeLifecycleError, match="execution_receipt_binding_mismatch"):
            outcome_lifecycle.measure(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                contract_digest=contract["digest"], evidence_context_hash="compound-evidence",
                measurement_context=ctx, observed={"revenue": 150},
            )
        ledger_row.receipt_json = original_receipt
        db.session.commit()

        evidence_row = ExecutionEvidence.query.filter_by(
            organization_id=org.id, execution_key=execution_key,
            stage="specialist.execution_submitted",
        ).first()
        assert evidence_row is not None
        original_evidence = evidence_row.receipt_json
        evidence_row.receipt_json = json.dumps({"provider_id": "grok", "external_task_id": "wrong"})
        db.session.commit()
        with pytest.raises(OutcomeLifecycleError, match="execution_evidence_binding_mismatch"):
            outcome_lifecycle.measure(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                contract_digest=contract["digest"], evidence_context_hash="compound-evidence",
                measurement_context=ctx, observed={"revenue": 150},
            )
        evidence_row.receipt_json = original_evidence
        db.session.commit()
        measured = outcome_lifecycle.measure(
            organization_id=org.id, execution_key=execution_key, provider_id="manus",
            contract_digest=contract["digest"], evidence_context_hash="compound-evidence",
            measurement_context=ctx,
            observed={"revenue": 150, "execution_key": execution_key, "provider_id": "manus"},
        )
        assert measured["status"] == "measured"
        assert measured["measurement_count"] == 1

        with pytest.raises(OutcomeLifecycleError, match="outcome_measurement_replay"):
            outcome_lifecycle.measure(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                contract_digest=contract["digest"], evidence_context_hash="compound-evidence",
                measurement_context=ctx,
                observed={"revenue": 150, "execution_key": execution_key, "provider_id": "manus"},
            )


def test_completed_chain_rejects_cross_tenant_outcome_binding():
    with application.app_context():
        db.create_all()
        owner = _org()
        attacker = _org()
        execution_key = f"exec-cross-{uuid.uuid4().hex}"
        contract = OutcomeControlService().contract(
            decision={"decision_id": "cross", "task_id": "cross-task", "organization_id": owner.id, "digest": "x" * 64},
            expected_metrics=[{"metric": "revenue", "baseline": 1, "target": 2}],
        )
        with pytest.raises(OutcomeLifecycleError, match="outcome_contract_tenant_mismatch"):
            outcome_lifecycle.bind_contract(
                contract=contract, organization_id=attacker.id, execution_key=execution_key,
                provider_id="manus", evidence_context_hash="cross", measurement_context={"window": "1d"},
            )
