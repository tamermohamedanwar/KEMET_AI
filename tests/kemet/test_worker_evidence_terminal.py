import uuid
from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.governed_worker import GovernedWorker
from app.core.execution_evidence import execution_evidence

class Queue:
    def __init__(self, claimed): self.claimed, self.failed, self.cancelled = claimed, [], []
    def claim(self, **kwargs): return self.claimed
    def fail(self, job_id, error, **kwargs): self.failed.append((job_id, error)); return {"ok": True}
    def cancel(self, job_id, **kwargs): self.cancelled.append(job_id); return True

class Coordinator:
    def admit(self, **kwargs): return {"allowed": True, "reason": "admitted"}
    def is_cancelled(self, **kwargs): return False

def test_terminal_failure_is_persisted_as_execution_evidence():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Evidence {uid}", slug=f"evidence-{uid}")
        db.session.add(org); db.session.commit()
        key = f"exec-{uid}"
        queue = Queue({"job_id": 701, "job_key": key, "organization_id": org.id,
                       "payload": {"trace_id": "trace-1", "correlation_id": "corr-1"}})
        result = GovernedWorker(queue=queue, coordinator=Coordinator()).process_one(
            worker_id="worker-a", plan_resolver=lambda payload: None)
        assert result["status"] == "blocked"
        history = execution_evidence.history(organization_id=org.id, execution_key=key)
        stages = {(item["stage"], item["status"]) for item in history}
        assert ("queue.claimed", "claimed") in stages
        assert ("worker.terminal", "blocked") in stages
        terminal = [item for item in history if item["stage"] == "worker.terminal"]
        assert terminal[0]["receipt"]["reason"] == "plan_missing"

# Evidence regression keeps terminal governance outcomes durable and tenant-scoped.
# Full suite is the authoritative validation gate for this milestone.

# End of regression module.
