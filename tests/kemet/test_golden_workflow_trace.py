import uuid

import pytest

from app.core.golden_workflow_trace import GoldenWorkflowTraceError, golden_workflow_trace
from app.core.workflow_runtime import WorkflowState


def test_golden_trace_requires_terminal_completion():
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.workflow_transition import WorkflowTransitionRecord
    from app.models.automation_execution_ledger import AutomationExecutionLedger
    from app.models.execution_evidence import ExecutionEvidence
    from app.models.automation_outcome import AutomationOutcome

    with application.app_context():
        unique = uuid.uuid4().hex
        org = Organization(name=f"Trace Org {unique}", slug=f"trace-{unique}")
        db.session.add(org)
        db.session.commit()
        key = f"trace-{unique}"
        db.session.add(WorkflowTransitionRecord(
            organization_id=org.id, job_id="9001", workflow_id="wf-trace",
            execution_id="exec-trace", idempotency_key=key,
            from_state=WorkflowState.PROCESSING, to_state=WorkflowState.COMPLETED,
            reason="completed", actor="test", execution_key=key,
        ))
        db.session.add(AutomationExecutionLedger(
            organization_id=org.id, execution_key=key, plan_hash="plan-1",
            job_id=9001, status="completed", receipt_json="{}",
        ))
        db.session.add(ExecutionEvidence(
            organization_id=org.id, execution_key=key, job_id=9001,
            workflow_id="wf-trace", stage="runtime.finished", status="completed",
            evidence_key=f"{key}:runtime.finished", receipt_json="{}",
        ))
        db.session.add(AutomationOutcome(
            organization_id=org.id, job_id=9001, workflow_id="wf-trace",
            status="completed", executed=True, receipt_json="{}",
        ))
        db.session.commit()
        result = golden_workflow_trace.assert_terminal_completed(
            organization_id=org.id, job_id=9001, execution_key=key, plan_hash="plan-1"
        )
        assert result["ok"] is True
        assert result["status"] == "completed"


def test_golden_trace_rejects_missing_completion_evidence():
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.workflow_transition import WorkflowTransitionRecord
    from app.models.automation_execution_ledger import AutomationExecutionLedger
    from app.models.automation_outcome import AutomationOutcome

    with application.app_context():
        unique = uuid.uuid4().hex
        org = Organization(name=f"Trace Evidence {unique}", slug=f"trace-evidence-{unique}")
        db.session.add(org)
        db.session.commit()
        key = f"trace-evidence-{unique}"
        db.session.add(WorkflowTransitionRecord(
            organization_id=org.id, job_id="9002", workflow_id="wf-trace",
            execution_id="exec-trace", idempotency_key=key,
            from_state=WorkflowState.PROCESSING, to_state=WorkflowState.COMPLETED,
            reason="completed", actor="test", execution_key=key,
        ))
        db.session.add(AutomationExecutionLedger(
            organization_id=org.id, execution_key=key, plan_hash="plan-2",
            job_id=9002, status="completed", receipt_json="{}",
        ))
        db.session.add(AutomationOutcome(
            organization_id=org.id, job_id=9002, workflow_id="wf-trace",
            status="completed", executed=True, receipt_json="{}",
        ))
        db.session.commit()
        with pytest.raises(GoldenWorkflowTraceError, match="golden_trace_completion_evidence_missing"):
            golden_workflow_trace.assert_terminal_completed(
                organization_id=org.id, job_id=9002, execution_key=key, plan_hash="plan-2"
            )


def test_golden_trace_reconciles_ledger_decision_identity():
    import json
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.workflow_transition import WorkflowTransitionRecord
    from app.models.automation_execution_ledger import AutomationExecutionLedger
    from app.models.execution_evidence import ExecutionEvidence
    from app.models.automation_outcome import AutomationOutcome

    with application.app_context():
        unique = uuid.uuid4().hex
        org = Organization(name=f"Trace Identity {unique}", slug=f"trace-identity-{unique}")
        db.session.add(org)
        db.session.commit()
        key = f"trace-identity-{unique}"
        identity = {"decision_hash": "decision-1", "approval_id": "42"}
        db.session.add(WorkflowTransitionRecord(
            organization_id=org.id, job_id="9003", workflow_id="wf-trace",
            execution_id="exec-trace", idempotency_key=key,
            from_state=WorkflowState.PROCESSING, to_state=WorkflowState.COMPLETED,
            reason="completed", actor="test", execution_key=key,
            decision_hash="decision-1", approval_id="42",
        ))
        db.session.add(AutomationExecutionLedger(
            organization_id=org.id, execution_key=key, plan_hash="plan-3",
            job_id=9003, status="completed",
            receipt_json=json.dumps({"execution_identity": identity}),
        ))
        db.session.add(ExecutionEvidence(
            organization_id=org.id, execution_key=key, job_id=9003,
            workflow_id="wf-trace", stage="runtime.finished", status="completed",
            evidence_key=f"{key}:runtime.finished", receipt_json="{}",
        ))
        db.session.add(AutomationOutcome(
            organization_id=org.id, job_id=9003, workflow_id="wf-trace",
            status="completed", executed=True,
            receipt_json=json.dumps({"execution_identity": {"execution_key": key, **identity}}),
        ))
        db.session.commit()
        result = golden_workflow_trace.assert_terminal_completed(
            organization_id=org.id, job_id=9003, execution_key=key, plan_hash="plan-3"
        )
        assert result["ok"] is True


def test_golden_trace_rejects_ledger_identity_mismatch():
    import json
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.workflow_transition import WorkflowTransitionRecord
    from app.models.automation_execution_ledger import AutomationExecutionLedger
    from app.models.execution_evidence import ExecutionEvidence
    from app.models.automation_outcome import AutomationOutcome

    with application.app_context():
        unique = uuid.uuid4().hex
        org = Organization(name=f"Trace Mismatch {unique}", slug=f"trace-mismatch-{unique}")
        db.session.add(org)
        db.session.commit()
        key = f"trace-mismatch-{unique}"
        db.session.add(WorkflowTransitionRecord(
            organization_id=org.id, job_id="9004", workflow_id="wf-trace",
            execution_id="exec-trace", idempotency_key=key,
            from_state=WorkflowState.PROCESSING, to_state=WorkflowState.COMPLETED,
            reason="completed", actor="test", execution_key=key,
            decision_hash="decision-expected", approval_id="43",
        ))
        db.session.add(AutomationExecutionLedger(
            organization_id=org.id, execution_key=key, plan_hash="plan-4",
            job_id=9004, status="completed",
            receipt_json=json.dumps({"execution_identity": {"decision_hash": "decision-wrong", "approval_id": "43"}}),
        ))
        db.session.add(ExecutionEvidence(
            organization_id=org.id, execution_key=key, job_id=9004,
            workflow_id="wf-trace", stage="runtime.finished", status="completed",
            evidence_key=f"{key}:runtime.finished", receipt_json="{}",
        ))
        db.session.add(AutomationOutcome(
            organization_id=org.id, job_id=9004, workflow_id="wf-trace",
            status="completed", executed=True, receipt_json="{}",
        ))
        db.session.commit()
        with pytest.raises(GoldenWorkflowTraceError, match="golden_trace_ledger_decision_hash_mismatch"):
            golden_workflow_trace.assert_terminal_completed(
                organization_id=org.id, job_id=9004, execution_key=key, plan_hash="plan-4"
            )


def test_golden_trace_rejects_outcome_identity_mismatch():
    import json
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.workflow_transition import WorkflowTransitionRecord
    from app.models.automation_execution_ledger import AutomationExecutionLedger
    from app.models.execution_evidence import ExecutionEvidence
    from app.models.automation_outcome import AutomationOutcome
    with application.app_context():
        unique = uuid.uuid4().hex
        org = Organization(name=f"Trace Outcome {unique}", slug=f"trace-outcome-{unique}")
        db.session.add(org)
        db.session.commit()
        key = f"trace-outcome-{unique}"
        db.session.add(WorkflowTransitionRecord(organization_id=org.id, job_id="9005", workflow_id="wf-trace", execution_id="exec-trace", idempotency_key=key, from_state=WorkflowState.PROCESSING, to_state=WorkflowState.COMPLETED, reason="completed", actor="test", execution_key=key, decision_hash="decision-5", approval_id="45"))
        db.session.add(AutomationExecutionLedger(organization_id=org.id, execution_key=key, plan_hash="plan-5", job_id=9005, status="completed", receipt_json=json.dumps({"execution_identity": {"decision_hash": "decision-5", "approval_id": "45"}})))
        db.session.add(ExecutionEvidence(organization_id=org.id, execution_key=key, job_id=9005, workflow_id="wf-trace", stage="runtime.finished", status="completed", evidence_key=f"{key}:runtime.finished", receipt_json="{}"))
        db.session.add(AutomationOutcome(organization_id=org.id, job_id=9005, workflow_id="wf-trace", status="completed", executed=True, receipt_json=json.dumps({"execution_identity": {"execution_key": key, "decision_hash": "wrong", "approval_id": "45"}})))
        db.session.commit()
        with pytest.raises(GoldenWorkflowTraceError, match="golden_trace_outcome_decision_hash_mismatch"):
            golden_workflow_trace.assert_terminal_completed(organization_id=org.id, job_id=9005, execution_key=key, plan_hash="plan-5")
