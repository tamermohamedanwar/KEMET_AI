import time
import uuid

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.automation_queue import AutomationQueue
from app.core.controlled_replay import ControlledReplayService
from app.core.execution.authorization import execution_authorization


def test_dead_letter_replay_requires_fresh_matching_authorization():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Replay {uid}", slug=f"replay-{uid}")
        db.session.add(org)
        db.session.commit()
        plan = {"plan_id": f"plan-{uid}", "action": "create_ticket", "organization_id": org.id}
        auth = execution_authorization.create_authorization(plan, approver_id=7)
        queue = AutomationQueue()
        created = queue.enqueue({"organization_id": org.id, "job_key": f"replay-{uid}", "plan": plan, "action": "create_ticket"})
        job = db.session.get(__import__("app.models.automation_queue", fromlist=["AutomationQueueJob"]).AutomationQueueJob, created["job_id"])
        job.status = "dead_letter"
        job.attempts = job.max_attempts
        db.session.commit()
        service = ControlledReplayService(queue)
        result = service.replay(job_id=job.id, authorization=auth, approver_id=7)
        assert result["ok"] is True
        assert result["status"] == "requeued_with_fresh_authorization"
        assert db.session.get(type(job), job.id).status == "queued"


def test_replay_rejects_missing_plan_context():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"ReplayMissing {uid}", slug=f"replay-missing-{uid}")
        db.session.add(org)
        db.session.commit()
        queue = AutomationQueue()
        created = queue.enqueue({"organization_id": org.id, "job_key": f"missing-{uid}"})
        from app.models.automation_queue import AutomationQueueJob
        job = db.session.get(AutomationQueueJob, created["job_id"])
        job.status = "dead_letter"
        db.session.commit()
        result = ControlledReplayService(queue).replay(job_id=job.id, authorization={"one_time": True, "token": "x"})
        assert result["status"] == "replay_plan_context_missing"
