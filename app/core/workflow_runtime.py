from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class WorkflowTransitionError(ValueError):
    pass


class WorkflowState:
    CREATED = "created"
    VALIDATED = "validated"
    PLANNED = "planned"
    SIMULATED = "simulated"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"


TERMINAL_STATES = frozenset({
    WorkflowState.COMPLETED,
    WorkflowState.FAILED,
    WorkflowState.CANCELLED,
    WorkflowState.EXPIRED,
    WorkflowState.REJECTED,
})

ALLOWED_TRANSITIONS = {
    WorkflowState.CREATED: {WorkflowState.VALIDATED, WorkflowState.WAITING_APPROVAL, WorkflowState.QUEUED, WorkflowState.CANCELLED},
    WorkflowState.VALIDATED: {WorkflowState.PLANNED, WorkflowState.FAILED, WorkflowState.CANCELLED},
    WorkflowState.PLANNED: {WorkflowState.SIMULATED, WorkflowState.WAITING_APPROVAL, WorkflowState.FAILED, WorkflowState.CANCELLED},
    WorkflowState.SIMULATED: {WorkflowState.WAITING_APPROVAL, WorkflowState.APPROVED, WorkflowState.FAILED, WorkflowState.CANCELLED},
    WorkflowState.WAITING_APPROVAL: {WorkflowState.APPROVED, WorkflowState.REJECTED, WorkflowState.EXPIRED, WorkflowState.CANCELLED},
    WorkflowState.APPROVED: {WorkflowState.QUEUED, WorkflowState.FAILED, WorkflowState.CANCELLED},
    WorkflowState.QUEUED: {WorkflowState.WAITING_APPROVAL, WorkflowState.PROCESSING, WorkflowState.EXPIRED, WorkflowState.CANCELLED},
    WorkflowState.PROCESSING: {WorkflowState.COMPLETED, WorkflowState.FAILED, WorkflowState.RETRYING, WorkflowState.AMBIGUOUS, WorkflowState.CANCELLED, WorkflowState.EXPIRED},
    WorkflowState.RETRYING: {WorkflowState.QUEUED, WorkflowState.FAILED, WorkflowState.EXPIRED, WorkflowState.CANCELLED},
    WorkflowState.FAILED: {WorkflowState.QUEUED, WorkflowState.CANCELLED},
    WorkflowState.AMBIGUOUS: {WorkflowState.PROCESSING, WorkflowState.FAILED, WorkflowState.CANCELLED},
}


@dataclass(frozen=True)
class WorkflowIdentity:
    organization_id: int
    job_id: str
    workflow_id: str
    execution_id: str
    idempotency_key: str


@dataclass(frozen=True)
class WorkflowTransition:
    identity: WorkflowIdentity
    from_state: str
    to_state: str
    reason: str | None = None
    metadata: dict[str, Any] | None = None


class UnifiedWorkflowRuntime:
    VERSION = "1.0"

    def can_transition(self, current: str, target: str) -> bool:
        return target in ALLOWED_TRANSITIONS.get(str(current), set())

    def transition(
        self,
        identity: WorkflowIdentity,
        current: str,
        target: str,
        *,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowTransition:
        current = str(current)
        target = str(target)
        if current not in ALLOWED_TRANSITIONS:
            raise WorkflowTransitionError("unknown_workflow_state")
        replay_authorized = bool((metadata or {}).get("replay_authorized"))
        if current in TERMINAL_STATES and not (current == WorkflowState.FAILED and target == WorkflowState.QUEUED and replay_authorized):
            raise WorkflowTransitionError("workflow_already_terminal")
        if not self.can_transition(current, target):
            raise WorkflowTransitionError(f"invalid_workflow_transition:{current}->{target}")
        if identity.organization_id <= 0:
            raise WorkflowTransitionError("organization_identity_required")
        if not identity.job_id or not identity.workflow_id or not identity.execution_id or not identity.idempotency_key:
            raise WorkflowTransitionError("workflow_identity_incomplete")
        return WorkflowTransition(identity, current, target, reason, dict(metadata or {}))

    def assert_not_terminal(self, state: str) -> None:
        if str(state) in TERMINAL_STATES:
            raise WorkflowTransitionError("workflow_already_terminal")

    def normalize_queue_state(self, state: str) -> str:
        mapping = {"leased": WorkflowState.PROCESSING, "dead_letter": WorkflowState.FAILED}
        return mapping.get(str(state), str(state))

    def normalize_execution_state(self, state: str) -> str:
        mapping = {"running": WorkflowState.PROCESSING}
        return mapping.get(str(state), str(state))


unified_workflow_runtime = UnifiedWorkflowRuntime()
