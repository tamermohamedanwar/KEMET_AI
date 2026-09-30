import json
import uuid
from datetime import datetime

import pytest

from app import db, create_app
from app.core.workflow_runtime import WorkflowState
from app.models.automation import AutomationApproval, AutomationExecution, AutomationWorkflow
from app.models.automation_queue import AutomationQueueJob
from app.services.automation_approval_service import automation_approval_service


def _setup_pending_rejection_case():
    unique = uuid.uuid4().hex
    workflow = AutomationWorkflow(organization_id=1, name=f"Reject Atomicity {unique}", trigger_type="manual", is_active=True)
    db.session.add(workflow)
    db.session.flush()
    execution = AutomationExecution(workflow_id=workflow.id, trigger_type="manual", idempotency_key=f"idem-{unique}", status="running", input_json="{}")
    db.session.add(execution)
    db.session.flush()
    job = AutomationQueueJob(organization_id=1, job_key=f"reject-{unique}", workflow_id=str(workflow.id), execution_id=str(execution.id), idempotency_key=execution.idempotency_key, workflow_state=WorkflowState.WAITING_APPROVAL, payload_json=json.dumps({"workflow_id": workflow.id, "execution_id": execution.id}), status="queued", priority=100, available_at=datetime.utcnow())
    db.session.add(job)
    db.session.flush()
    approval = AutomationApproval(organization_id=1, workflow_id=workflow.id, execution_id=execution.id, action_type="test_action", status="pending", request_json=json.dumps({"action": "test_action"}))
    db.session.add(approval)
    db.session.commit()
    return approval, execution, job


def test_rejection_commits_workflow_and_execution_atomically():
    app = create_app()
    with app.app_context():
        approval, execution, job = _setup_pending_rejection_case()
        result = automation_approval_service.reject(approval.id, decided_by=1, reason="denied")
        assert result["success"] is True
        db.session.expire_all()
        assert db.session.get(AutomationApproval, approval.id).status == "rejected"
        assert db.session.get(AutomationExecution, execution.id).status == "rejected"
        assert db.session.get(AutomationQueueJob, job.id).workflow_state == WorkflowState.REJECTED


def test_rejection_rolls_back_if_coordinator_transition_fails(monkeypatch):
    app = create_app()
    with app.app_context():
        approval, execution, job = _setup_pending_rejection_case()

        def fail_transition(*args, **kwargs):
            raise RuntimeError("coordinator_failure")

        monkeypatch.setattr(
            "app.services.automation_approval_service.workflow_coordinator.transition_approval",
            fail_transition,
        )
        with pytest.raises(RuntimeError, match="coordinator_failure"):
            automation_approval_service.reject(approval.id, decided_by=1, reason="denied")
        db.session.expire_all()
        assert db.session.get(AutomationApproval, approval.id).status == "pending"
        assert db.session.get(AutomationExecution, execution.id).status == "running"
        assert db.session.get(AutomationQueueJob, job.id).workflow_state == WorkflowState.WAITING_APPROVAL
