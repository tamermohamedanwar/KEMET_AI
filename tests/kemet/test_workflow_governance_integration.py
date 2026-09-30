import uuid

import pytest

from app.core.workflow_coordinator import workflow_coordinator
from app.core.workflow_runtime import WorkflowState, WorkflowTransitionError
from app.core.automation_queue import AutomationQueue


def test_coordinator_requires_approval_identity_for_approval_transition():
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.automation_queue import AutomationQueueJob

    with application.app_context():
        unique = uuid.uuid4().hex
        org = Organization(name=f"Workflow Org {unique}", slug=f"workflow-{unique}")
        db.session.add(org)
        db.session.commit()
        queue = AutomationQueue()
        created = queue.enqueue({
            "organization_id": org.id,
            "job_key": f"wf-{unique}",
            "workflow_id": "wf-1",
            "execution_id": "exec-1",
            "workflow_state": WorkflowState.WAITING_APPROVAL,
        })
        job = db.session.get(AutomationQueueJob, created["job_id"])
        with pytest.raises(ValueError, match="workflow_approval_identity_required"):
            workflow_coordinator.transition_job(
                job.id, WorkflowState.APPROVED, reason="test",
            )


def test_approval_to_queue_transition_is_durable():
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.workflow_transition import WorkflowTransitionRecord

    with application.app_context():
        unique = uuid.uuid4().hex
        org = Organization(name=f"Approval Flow {unique}", slug=f"approval-flow-{unique}")
        db.session.add(org)
        db.session.commit()
        queue = AutomationQueue()
        created = queue.enqueue({
            "organization_id": org.id,
            "job_key": f"approval-flow-{unique}",
            "workflow_id": "wf-flow",
            "execution_id": "exec-flow",
            "workflow_state": WorkflowState.WAITING_APPROVAL,
        })
        job_id = created["job_id"]
        workflow_coordinator.transition_job(
            job_id, WorkflowState.APPROVED, reason="approved",
            metadata={"approval_id": 42, "plan_hash": "plan-1", "execution_key": f"approval:{job_id}"},
        )
        workflow_coordinator.transition_job(
            job_id, WorkflowState.QUEUED, reason="queued",
            metadata={"approval_id": 42, "plan_hash": "plan-1", "execution_key": f"approval:{job_id}"},
        )
        history = WorkflowTransitionRecord.query.filter_by(job_id=str(job_id)).all()
        assert [row.to_state for row in history] == [WorkflowState.WAITING_APPROVAL, WorkflowState.APPROVED, WorkflowState.QUEUED]


def test_waiting_approval_job_cannot_be_claimed():
    from wsgi import application
    from app import db
    from app.models.organization import Organization

    with application.app_context():
        unique = uuid.uuid4().hex
        org = Organization(name=f"Approval Queue {unique}", slug=f"approval-{unique}")
        db.session.add(org)
        db.session.commit()
        queue = AutomationQueue()
        queue.enqueue({
            "organization_id": org.id,
            "job_key": f"approval-{unique}",
            "workflow_id": "wf-approval",
            "execution_id": "exec-approval",
            "workflow_state": WorkflowState.WAITING_APPROVAL,
        })
        assert queue.claim(worker_id="worker", organization_id=org.id) is None

def test_lease_recovery_is_durable_and_replay_visible():
    from datetime import datetime, timedelta
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.automation_queue import AutomationQueueJob
    from app.models.workflow_transition import WorkflowTransitionRecord

    with application.app_context():
        unique = uuid.uuid4().hex
        org = Organization(name=f"Recovery Org {unique}", slug=f"recovery-{unique}")
        db.session.add(org)
        db.session.commit()
        queue = AutomationQueue()
        created = queue.enqueue({
            "organization_id": org.id,
            "job_key": f"recovery-{unique}",
            "workflow_id": "wf-recovery",
            "execution_id": "exec-recovery",
        })
        queue.claim(worker_id="worker-1", lease_seconds=1, organization_id=org.id)
        job = db.session.get(AutomationQueueJob, created["job_id"])
        job.lease_until = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        assert queue.recover_expired() == 1
        rows = WorkflowTransitionRecord.query.filter_by(job_id=str(job.id)).all()
        assert [row.to_state for row in rows][-2:] == [WorkflowState.RETRYING, WorkflowState.QUEUED]



def test_coordinator_rejects_persisted_state_divergence():
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.automation_queue import AutomationQueueJob

    with application.app_context():
        unique = uuid.uuid4().hex
        org = Organization(name=f"Divergence Org {unique}", slug=f"divergence-{unique}")
        db.session.add(org)
        db.session.commit()
        queue = AutomationQueue()
        created = queue.enqueue({
            "organization_id": org.id,
            "job_key": f"divergence-{unique}",
            "workflow_id": "wf-divergence",
            "execution_id": "exec-divergence",
        })
        job = db.session.get(AutomationQueueJob, created["job_id"])
        job.workflow_state = WorkflowState.WAITING_APPROVAL
        db.session.flush()
        with pytest.raises(WorkflowTransitionError, match="workflow_persisted_state_mismatch"):
            workflow_coordinator.record_job_transition(
                job.id, WorkflowState.QUEUED, WorkflowState.PROCESSING,
                reason="tampered_state",
                metadata={"execution_key": job.job_key},
            )
        db.session.rollback()
