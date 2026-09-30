import pytest

from app.core.workflow_runtime import (
    WorkflowIdentity,
    WorkflowState,
    WorkflowTransitionError,
    UnifiedWorkflowRuntime,
)


def identity():
    return WorkflowIdentity(7, "job-1", "workflow-1", "execution-1", "idem-1")


def test_happy_path_preserves_governed_order():
    runtime = UnifiedWorkflowRuntime()
    states = [WorkflowState.CREATED, WorkflowState.VALIDATED, WorkflowState.PLANNED,
              WorkflowState.SIMULATED, WorkflowState.WAITING_APPROVAL,
              WorkflowState.APPROVED, WorkflowState.QUEUED, WorkflowState.PROCESSING,
              WorkflowState.COMPLETED]
    for current, target in zip(states, states[1:]):
        transition = runtime.transition(identity(), current, target)
        assert transition.to_state == target


def test_execution_cannot_skip_approval_to_processing():
    runtime = UnifiedWorkflowRuntime()
    with pytest.raises(WorkflowTransitionError, match="invalid_workflow_transition"):
        runtime.transition(identity(), WorkflowState.PLANNED, WorkflowState.PROCESSING)


def test_rejection_is_terminal_and_cannot_resume():
    runtime = UnifiedWorkflowRuntime()
    with pytest.raises(WorkflowTransitionError):
        runtime.transition(identity(), WorkflowState.REJECTED, WorkflowState.APPROVED)


def test_retry_and_ambiguity_are_explicit_recovery_states():
    runtime = UnifiedWorkflowRuntime()
    assert runtime.can_transition(WorkflowState.PROCESSING, WorkflowState.RETRYING)
    assert runtime.can_transition(WorkflowState.PROCESSING, WorkflowState.AMBIGUOUS)
    assert runtime.can_transition(WorkflowState.AMBIGUOUS, WorkflowState.PROCESSING)


def test_identity_is_required_and_tenant_bound():
    runtime = UnifiedWorkflowRuntime()
    bad = WorkflowIdentity(0, "job", "wf", "exec", "idem")
    with pytest.raises(WorkflowTransitionError, match="organization_identity_required"):
        runtime.transition(bad, WorkflowState.CREATED, WorkflowState.VALIDATED)


def test_connector_states_normalize_to_canonical_states():
    runtime = UnifiedWorkflowRuntime()
    assert runtime.normalize_queue_state("leased") == WorkflowState.PROCESSING
    assert runtime.normalize_queue_state("dead_letter") == WorkflowState.FAILED
    assert runtime.normalize_execution_state("running") == WorkflowState.PROCESSING


def test_waiting_approval_cannot_be_claimed_as_work():
    runtime = UnifiedWorkflowRuntime()
    assert runtime.can_transition(WorkflowState.WAITING_APPROVAL, WorkflowState.APPROVED)
    assert not runtime.can_transition(WorkflowState.WAITING_APPROVAL, WorkflowState.PROCESSING)


def test_terminal_states_are_fail_closed():
    runtime = UnifiedWorkflowRuntime()
    for state in (WorkflowState.COMPLETED, WorkflowState.FAILED, WorkflowState.CANCELLED, WorkflowState.EXPIRED, WorkflowState.REJECTED):
        with pytest.raises(WorkflowTransitionError):
            runtime.assert_not_terminal(state)


def test_terminal_state_cannot_be_resurrected():
    runtime = UnifiedWorkflowRuntime()
    identity_value = identity()
    for state in (WorkflowState.COMPLETED, WorkflowState.FAILED, WorkflowState.CANCELLED, WorkflowState.EXPIRED, WorkflowState.REJECTED):
        for target in (WorkflowState.QUEUED, WorkflowState.PROCESSING, WorkflowState.COMPLETED):
            with pytest.raises(WorkflowTransitionError):
                runtime.transition(identity_value, state, target)
