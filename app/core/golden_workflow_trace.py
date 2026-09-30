from __future__ import annotations

import json
from typing import Any

from app.models.automation_execution_ledger import AutomationExecutionLedger
from app.models.automation_outcome import AutomationOutcome
from app.models.execution_evidence import ExecutionEvidence
from app.models.workflow_transition import WorkflowTransitionRecord
from app.core.workflow_runtime import WorkflowState


class GoldenWorkflowTraceError(ValueError):
    pass


class GoldenWorkflowTrace: 
    VERSION = "1.0"

    def inspect(self, *, organization_id: int, job_id: int, execution_key: str) -> dict[str, Any]:
        org = int(organization_id)
        jid = str(job_id)
        key = str(execution_key)
        transitions = WorkflowTransitionRecord.query.filter_by(organization_id=org, job_id=jid).order_by(WorkflowTransitionRecord.id.asc()).all()
        ledger = AutomationExecutionLedger.query.filter_by(organization_id=org, execution_key=key).first()
        evidence = ExecutionEvidence.query.filter_by(organization_id=org, execution_key=key).order_by(ExecutionEvidence.id.asc()).all()
        outcomes = AutomationOutcome.query.filter_by(organization_id=org, job_id=int(job_id)).order_by(AutomationOutcome.id.asc()).all()
        return {
            "organization_id": org,
            "job_id": int(job_id),
            "execution_key": key,
            "transitions": transitions,
            "ledger": ledger,
            "evidence": evidence,
            "outcomes": outcomes,
        }

    def assert_terminal_completed(self, *, organization_id: int, job_id: int, execution_key: str, plan_hash: str | None = None) -> dict[str, Any]:
        trace = self.inspect(organization_id=organization_id, job_id=job_id, execution_key=execution_key)
        transitions = trace["transitions"]
        ledger = trace["ledger"]
        evidence = trace["evidence"]
        outcomes = trace["outcomes"]
        if not transitions or transitions[-1].to_state != WorkflowState.COMPLETED:
            raise GoldenWorkflowTraceError("golden_trace_terminal_state_mismatch")
        if not ledger:
            raise GoldenWorkflowTraceError("golden_trace_ledger_missing")
        if str(ledger.execution_key) != str(execution_key):
            raise GoldenWorkflowTraceError("golden_trace_execution_key_mismatch")
        if plan_hash and str(ledger.plan_hash) != str(plan_hash):
            raise GoldenWorkflowTraceError("golden_trace_plan_hash_mismatch")
        transition_keys = {str(row.execution_key) for row in transitions if row.execution_key}
        if transition_keys and transition_keys != {str(execution_key)}:
            raise GoldenWorkflowTraceError("golden_trace_transition_identity_mismatch")
        decision_hashes = {str(row.decision_hash) for row in transitions if row.decision_hash}
        approval_ids = {str(row.approval_id) for row in transitions if row.approval_id}
        if len(decision_hashes) > 1:
            raise GoldenWorkflowTraceError("golden_trace_decision_identity_mismatch")
        if len(approval_ids) > 1:
            raise GoldenWorkflowTraceError("golden_trace_approval_identity_mismatch")
        ledger_receipt = json.loads(ledger.receipt_json or "{}")
        ledger_identity = ledger_receipt.get("execution_identity") or {}
        ledger_decision = str(ledger_identity.get("decision_hash") or "")
        ledger_approval = str(ledger_identity.get("approval_id") or "")
        if decision_hashes and ledger_decision != next(iter(decision_hashes)):
            raise GoldenWorkflowTraceError("golden_trace_ledger_decision_hash_mismatch")
        if approval_ids and ledger_approval != next(iter(approval_ids)):
            raise GoldenWorkflowTraceError("golden_trace_ledger_approval_id_mismatch")
        if not outcomes:
            raise GoldenWorkflowTraceError("golden_trace_outcome_missing")
        terminal_evidence = [row for row in evidence if row.evidence_key == f"{execution_key}:runtime.finished"]
        if not terminal_evidence:
            raise GoldenWorkflowTraceError("golden_trace_completion_evidence_missing")
        for row in terminal_evidence:
            if row.job_id is not None and int(row.job_id) != int(job_id):
                raise GoldenWorkflowTraceError("golden_trace_evidence_job_mismatch")
            if row.workflow_id and transitions[-1].workflow_id and str(row.workflow_id) != str(transitions[-1].workflow_id):
                raise GoldenWorkflowTraceError("golden_trace_evidence_workflow_mismatch")
        for outcome in outcomes:
            if outcome.job_id is not None and int(outcome.job_id) != int(job_id):
                raise GoldenWorkflowTraceError("golden_trace_outcome_job_mismatch")
            if outcome.workflow_id and transitions[-1].workflow_id and str(outcome.workflow_id) != str(transitions[-1].workflow_id):
                raise GoldenWorkflowTraceError("golden_trace_outcome_workflow_mismatch")
            receipt = json.loads(outcome.receipt_json or "{}")
            identity = receipt.get("execution_identity") or {}
            if identity and str(identity.get("execution_key") or "") != str(execution_key):
                raise GoldenWorkflowTraceError("golden_trace_outcome_execution_key_mismatch")
            if decision_hashes and identity.get("decision_hash") and str(identity["decision_hash"]) != next(iter(decision_hashes)):
                raise GoldenWorkflowTraceError("golden_trace_outcome_decision_hash_mismatch")
            if approval_ids and identity.get("approval_id") and str(identity["approval_id"]) != next(iter(approval_ids)):
                raise GoldenWorkflowTraceError("golden_trace_outcome_approval_id_mismatch")
        return {
            "ok": True,
            "organization_id": trace["organization_id"],
            "job_id": trace["job_id"],
            "execution_key": trace["execution_key"],
            "transition_count": len(transitions),
            "evidence_count": len(evidence),
            "outcome_count": len(outcomes),
            "ledger_status": ledger.status,
            "status": "completed",
        }


golden_workflow_trace = GoldenWorkflowTrace()
