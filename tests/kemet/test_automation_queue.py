from datetime import datetime, timedelta
import uuid

from app.core.automation_queue import AutomationQueue
from app.core.automation_scheduler import AutomationScheduler


def test_scheduler_envelope_is_non_executing_and_deterministic():
    scheduler = AutomationScheduler()
    intent = {"organization_id": 4, "event_id": "evt-1", "trigger_id": "trigger-1",
              "workflow_id": "workflow-1", "priority": 10,
              "execution": {"approval_required": True}}
    first = scheduler.envelope(intent, correlation_id="corr", trace_id="trace")
    second = scheduler.envelope(intent, correlation_id="corr", trace_id="trace")
    assert first["job_key"] == second["job_key"]
    assert first["execution"]["executed"] is False
    assert first["execution"]["external_execution"] is False
    assert first["execution"]["database_mutation"] is False
    assert first["execution"]["approval_required"] is True


def test_scheduler_job_key_is_tenant_safe():
    scheduler = AutomationScheduler()
    base = {"event_id": "evt", "trigger_id": "trigger", "workflow_id": "w"}
    a = scheduler.envelope({"organization_id": 1, **base})
    b = scheduler.envelope({"organization_id": 2, **base})
    assert a["job_key"] != b["job_key"]


def test_queue_lease_retry_backoff_dead_letter_and_owner():
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.automation_queue import AutomationQueueJob

    with application.app_context():
        db.create_all()
        unique = uuid.uuid4().hex
        org = Organization(name=f"Queue Test Org {unique}", slug=f"queue-test-{unique}")
        db.session.add(org)
        db.session.commit()
        queue = AutomationQueue()
        envelope = {"organization_id": org.id, "job_key": f"job-queue-test-{unique}",
                    "event_id": "evt", "trigger_id": "trg", "workflow_id": "wf",
                    "priority": -1000, "max_attempts": 2}
        created = queue.enqueue(envelope)
        assert created["accepted"] is True
        duplicate = queue.enqueue(envelope)
        assert duplicate["status"] == "deduplicated"
        claim = queue.claim(worker_id="worker-1", lease_seconds=30)
        assert claim["job_id"] == created["job_id"]
        assert claim["attempt"] == 1
        assert queue.fail(created["job_id"], "bad-owner", worker_id="worker-2")["status"] == "lease_owner_mismatch"
        retry = queue.fail(created["job_id"], "temporary", worker_id="worker-1")
        assert retry["status"] == "requeued"
        job = db.session.get(AutomationQueueJob, created["job_id"])
        job.available_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        claim2 = queue.claim(worker_id="worker-1", lease_seconds=30)
        assert claim2["job_id"] == created["job_id"]
        assert claim2["attempt"] == 2
        final = queue.fail(created["job_id"], "permanent", worker_id="worker-1")
        assert final["status"] == "dead_letter"


def test_queue_deadline_is_persisted():
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.automation_queue import AutomationQueueJob
    with application.app_context():
        db.create_all()
        unique = uuid.uuid4().hex
        org = Organization(name=f"Deadline Org {unique}", slug=f"deadline-{unique}")
        db.session.add(org)
        db.session.commit()
        queue = AutomationQueue()
        result = queue.enqueue({"organization_id": org.id, "job_key": f"deadline-{unique}"}, deadline_seconds=30)
        row = db.session.get(AutomationQueueJob, result["job_id"])
        assert row.deadline_at is not None
