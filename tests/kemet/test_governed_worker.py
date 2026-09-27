from app.core.governed_worker import GovernedWorker


class FakeQueue:
    def __init__(self, claimed=None):
        self.claimed = claimed
        self.completed = []
        self.cancelled = []
        self.failed = []

    def claim(self, **kwargs):
        return self.claimed

    def complete(self, job_id, **kwargs):
        self.completed.append(job_id)
        return True

    def cancel(self, job_id, **kwargs):
        self.cancelled.append(job_id)
        return True

    def fail(self, job_id, error, **kwargs):
        self.failed.append((job_id, error))
        return {"ok": True, "status": "requeued"}


class FakeRuntime:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute(self, plan, **kwargs):
        self.calls.append((plan, kwargs))
        return self.result


def test_worker_is_idle_without_jobs():
    result = GovernedWorker(queue=FakeQueue(), runtime=FakeRuntime({})).process_one(
        worker_id="w1", plan_resolver=lambda payload: None)
    assert result["status"] == "idle"
    assert result["executed"] is False


def test_worker_requires_resolved_plan_before_runtime():
    queue = FakeQueue({"job_id": 7, "payload": {}})
    runtime = FakeRuntime({"status": "completed", "executed": True})
    result = GovernedWorker(queue=queue, runtime=runtime).process_one(
        worker_id="w1", plan_resolver=lambda payload: None)
    assert result["status"] == "blocked"
    assert runtime.calls == []
    assert queue.failed == [(7, "plan_missing")]


def test_worker_executes_only_through_runtime_and_completes_queue():
    queue = FakeQueue({"job_id": 9, "payload": {"actor_id": "42"}})
    runtime = FakeRuntime({"status": "completed", "executed": True})
    plan = object()
    result = GovernedWorker(queue=queue, runtime=runtime).process_one(
        worker_id="w1", plan_resolver=lambda payload: plan)
    assert result["status"] == "completed"
    assert result["executed"] is True
    assert queue.completed == [9]
    assert runtime.calls[0][0] is plan


def test_worker_cancels_governance_block_without_execution():
    queue = FakeQueue({"job_id": 11, "payload": {}})
    runtime = FakeRuntime({"status": "blocked", "executed": False})
    result = GovernedWorker(queue=queue, runtime=runtime).process_one(
        worker_id="w1", plan_resolver=lambda payload: object())
    assert result["status"] == "blocked"
    assert result["executed"] is False
    assert queue.cancelled == [11]


def test_worker_rejects_expired_deadline_before_plan_resolution():
    queue = FakeQueue({"job_id": 12, "payload": {}, "deadline_at": "2000-01-01T00:00:00"})
    runtime = FakeRuntime({"status": "completed", "executed": True})
    calls = []
    result = GovernedWorker(queue=queue, runtime=runtime).process_one(
        worker_id="w1", plan_resolver=lambda payload: calls.append(payload))
    assert result["status"] == "deadline_exceeded"
    assert calls == []
    assert runtime.calls == []


def test_worker_binds_execution_to_durable_ledger():
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.subscription import Subscription
    from app.core.execution_ledger import execution_ledger
    from app.core.automation_control_plane import AutomationPlan, AutomationStep

    with application.app_context():
        db.create_all()
        import uuid
        uid = uuid.uuid4().hex
        org = Organization(name=f"Worker Ledger {uid}", slug=f"worker-ledger-{uid}")
        db.session.add(org)
        db.session.flush()
        db.session.add(Subscription(organization_id=org.id, plan="business", status="active"))
        db.session.commit()
        queue = FakeQueue({"job_id": 21, "job_key": f"exec-{uid}",
                           "organization_id": org.id, "payload": {}})
        runtime = FakeRuntime({"status": "completed", "executed": True,
                               "receipt": {"executed": True}})
        plan = AutomationPlan(
            plan_id=f"plan-{uid}", organization_id=org.id, trigger="test",
            steps=(AutomationStep(step_id="s1", action="create_ticket"),),
            dry_run=False,
        )
        result = GovernedWorker(queue=queue, runtime=runtime).process_one(
            worker_id="w1", plan_resolver=lambda payload: plan)
        saved = execution_ledger.get(organization_id=org.id, execution_key=f"exec-{uid}")
        assert result["status"] == "completed"
        assert saved["status"] == "completed"





def test_worker_uses_execution_status_not_business_status():
    queue = FakeQueue({"job_id": 31, "payload": {"actor_id": "42"}})
    runtime = FakeRuntime({
        "status": "processing",
        "execution_status": "completed",
        "business_status": "processing",
        "executed": True,
    })
    result = GovernedWorker(queue=queue, runtime=runtime).process_one(
        worker_id="w1", plan_resolver=lambda payload: object())
    assert result["status"] == "completed"
    assert result["executed"] is True
    assert queue.completed == [31]
    assert queue.failed == []
