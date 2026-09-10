from datetime import datetime, timedelta
import uuid

from wsgi import application
from app import db
from app.models.organization import Organization
from app.models.automation_queue import AutomationQueueJob
from app.core.automation_queue import AutomationQueue
from app.core.worker_coordination import WorkerCoordinator


def _prepare(org_id, key):
    queue = AutomationQueue()
    created = queue.enqueue({"organization_id": org_id, "job_key": key,
                             "event_id": key, "trigger_id": "t", "workflow_id": "w"})
    now = datetime.utcnow()
    AutomationQueueJob.query.filter(
        AutomationQueueJob.status == "queued",
        AutomationQueueJob.id != created["job_id"],
    ).update({"available_at": now + timedelta(hours=1)}, synchronize_session=False)
    db.session.commit()
    return queue, created


def test_admission_enforces_tenant_limit():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Coord {uid}", slug=f"coord-{uid}")
        db.session.add(org)
        db.session.commit()
        queue, created = _prepare(org.id, f"coord-job-{uid}")
        claim = queue.claim(worker_id="coord-worker", organization_id=org.id)
        assert claim["job_id"] == created["job_id"]
        result = WorkerCoordinator().admit(organization_id=org.id, org_limit=1)
        assert result["allowed"] is False
        assert result["reason"] == "organization_concurrency_limit"


def test_heartbeat_requires_lease_owner():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Heartbeat {uid}", slug=f"heartbeat-{uid}")
        db.session.add(org)
        db.session.commit()
        queue, created = _prepare(org.id, f"heartbeat-job-{uid}")
        claim = queue.claim(worker_id="owner", lease_seconds=5, organization_id=org.id)
        assert claim["job_id"] == created["job_id"]
        coordinator = WorkerCoordinator()
        assert coordinator.heartbeat(job_id=created["job_id"], worker_id="intruder") is False
        assert coordinator.heartbeat(job_id=created["job_id"], worker_id="owner", lease_seconds=90) is True
        job = db.session.get(AutomationQueueJob, created["job_id"])
        assert job.lease_owner == "owner"
        assert job.lease_until > datetime.utcnow() + timedelta(seconds=80)


def test_cancellation_is_visible_to_owner():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Cancel {uid}", slug=f"cancel-{uid}")
        db.session.add(org)
        db.session.commit()
        queue, created = _prepare(org.id, f"cancel-job-{uid}")
        claim = queue.claim(worker_id="worker-cancel", organization_id=org.id)
        coordinator = WorkerCoordinator()
        assert claim["job_id"] == created["job_id"]
        assert coordinator.request_cancel(job_id=created["job_id"], requester="admin") is True
        assert coordinator.is_cancelled(job_id=created["job_id"], worker_id="worker-cancel") is True
