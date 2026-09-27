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
        created = queue.enqueue({"organization_id": org.id, "job_key": f"replay-{uid}", "workflow_id": f"wf-{uid}", "plan": plan, "action": "create_ticket"})
        job = db.session.get(__import__("app.models.automation_queue", fromlist=["AutomationQueueJob"]).AutomationQueueJob, created["job_id"])
        job.status = "dead_letter"
        job.attempts = job.max_attempts
        db.session.commit()
        service = ControlledReplayService(queue)
        result = service.replay(job_id=job.id, authorization=auth, approver_id=7)
        assert result["ok"] is True
        assert result["status"] == "requeued_with_fresh_authorization"
        saved = db.session.get(type(job), job.id)
        assert saved.status == "queued"
        payload = __import__("json").loads(saved.payload_json or "{}")
        assert payload["authorization"]["token"] != auth["token"]
        assert payload["execution_plan"]["plan_hash"] if "plan_hash" in payload["execution_plan"] else True
        assert payload["execution_plan"]["action"] == plan["action"]
        assert execution_authorization.consume(auth, plan=plan, action=plan["action"]) is True
        assert execution_authorization.consume(auth, plan=plan, action=plan["action"]) is False


def test_replay_rejects_missing_plan_context():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"ReplayMissing {uid}", slug=f"replay-missing-{uid}")
        db.session.add(org)
        db.session.commit()
        queue = AutomationQueue()
        created = queue.enqueue({"organization_id": org.id, "job_key": f"missing-{uid}", "workflow_id": f"wf-{uid}"})
        from app.models.automation_queue import AutomationQueueJob
        job = db.session.get(AutomationQueueJob, created["job_id"])
        job.status = "dead_letter"
        db.session.commit()
        result = ControlledReplayService(queue).replay(job_id=job.id, authorization={"one_time": True, "token": "x"})
        assert result["status"] == "replay_plan_context_missing"


def test_replay_binds_fresh_authorization_for_real_worker_execution():
    import json
    from app.models.subscription import Subscription
    from app.models.automation_queue import AutomationQueueJob
    from app.core.governed_worker import GovernedWorker
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"ReplayE2E {uid}", slug=f"replay-e2e-{uid}")
        db.session.add(org)
        db.session.flush()
        db.session.add(Subscription(organization_id=org.id, plan="business", status="active"))
        db.session.commit()
        key = f"replay-e2e-{uid}"
        plan = {"plan_id": f"plan-{uid}", "action": "check_order", "organization_id": org.id,
                "execution_key": key, "parameters": {"order_id": f"ORDER-{uid}"}}
        auth = execution_authorization.create_authorization(plan, approver_id=7)
        queue = AutomationQueue()
        created = queue.enqueue({"organization_id": org.id, "job_key": key,
            "execution_id": f"exec-{uid}", "idempotency_key": key,
            "workflow_id": f"wf-{uid}", "workflow_state": "queued", "priority": 0})
        queue.bind_execution_envelope(created["job_id"], plan=plan, authorization=auth)
        job = db.session.get(AutomationQueueJob, created["job_id"])
        job.workflow_state = "failed"
        job.status = "dead_letter"
        db.session.commit()
        replay = ControlledReplayService(queue).replay(job_id=job.id, authorization=auth, approver_id=7)
        assert replay["ok"] is True, replay
        saved = db.session.get(AutomationQueueJob, job.id)
        payload = json.loads(saved.payload_json)
        assert payload["authorization"]["token"] != auth["token"]
        result = GovernedWorker().process_one(worker_id=f"replay-worker-{uid}",
            plan_resolver=lambda payload: (_ for _ in ()).throw(AssertionError("resolver")))
        assert result["status"] == "completed", result
        assert result["executed"] is True
        assert db.session.get(AutomationQueueJob, job.id).workflow_state == "completed"


def test_real_worker_rejects_durable_plan_tampering_before_action():
    import json
    from app.models.subscription import Subscription
    from app.models.automation_queue import AutomationQueueJob
    from app.core.governed_worker import GovernedWorker
    from app.automation.action_registry import registry
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"ReplayTamper {uid}", slug=f"replay-tamper-{uid}")
        db.session.add(org)
        db.session.flush()
        db.session.add(Subscription(organization_id=org.id, plan="business", status="active"))
        db.session.commit()
        key = f"tamper-{uid}"
        plan = {"plan_id": f"plan-{uid}", "action": "check_order", "organization_id": org.id,
                "execution_key": key, "parameters": {"order_id": f"SAFE-{uid}"}}
        auth = execution_authorization.create_authorization(plan, approver_id=7)
        for pending in AutomationQueueJob.query.filter(AutomationQueueJob.status.in_(["queued", "leased"])).all():
            pending.status = "cancelled"
            pending.workflow_state = "cancelled"
        db.session.commit()
        queue = AutomationQueue()
        created = queue.enqueue({"organization_id": org.id, "job_key": key, "execution_id": f"exec-{uid}",
            "idempotency_key": key, "workflow_id": f"wf-{uid}", "workflow_state": "queued"})
        queue.bind_execution_envelope(created["job_id"], plan=plan, authorization=auth)
        job = db.session.get(AutomationQueueJob, created["job_id"])
        payload = json.loads(job.payload_json)
        payload["execution_plan"]["parameters"]["order_id"] = f"ATTACK-{uid}"
        job.payload_json = json.dumps(payload)
        db.session.commit()
        called = {"value": False}
        original = registry.execute
        def blocked_execute(*args, **kwargs):
            called["value"] = True
            return {"success": True}
        registry.execute = blocked_execute
        try:
            result = GovernedWorker().process_one(worker_id=f"tamper-worker-{uid}",
                plan_resolver=lambda payload: (_ for _ in ()).throw(AssertionError("resolver")))
        finally:
            registry.execute = original
        print("TAMPER_RESULT", result)
        assert result["status"] == "blocked", result
        assert called["value"] is False
        db.session.expire_all()
        saved = db.session.get(AutomationQueueJob, job.id)
        assert saved.workflow_state == "failed"


def test_salla_failure_retry_dead_letter_replay_and_single_receipt(monkeypatch):
    from wsgi import application
    import json
    from datetime import datetime
    from app import db
    from app.core.governed_worker import GovernedWorker
    from app.core.execution_evidence import execution_evidence
    from app.core.execution_ledger import execution_ledger
    from app.models.automation import AutomationExecution
    from app.models.organization import Organization
    from app.models.subscription import Subscription
    from app.models.automation_queue import AutomationQueueJob
    from app.services.automation_approval_service import automation_approval_service
    from app.services.salla_connector_service import SallaConnectorService

    with application.app_context():
        org = Organization(name=f"ReplaySalla {uuid.uuid4().hex}", slug=f"replay-salla-{uuid.uuid4().hex}")
        db.session.add(org)
        db.session.flush()
        db.session.add(Subscription(organization_id=org.id, plan="business", status="active"))
        db.session.commit()
        org_id = org.id

        event = SallaConnectorService.normalize_webhook(
            organization_id=org_id,
            payload={"event": "order.created", "data": {"id": f"replay-salla-{uuid.uuid4().hex}", "customer": {"name": "Replay"}}},
        )
        materialized = SallaConnectorService.materialize_webhook_workflow(
            organization_id=org_id, event=event, requested_by=None
        )
        assert automation_approval_service.approve(materialized["approval_id"], decided_by=1)["success"] is True
        job = db.session.get(AutomationQueueJob, materialized["job_id"])
        payload = json.loads(job.payload_json)
        assert payload["execution_identity"]["idempotency_key"] == materialized["idempotency_key"]
        monkeypatch.setenv(f"KEMET_SALLA_ORG_{org_id}_ACCESS_TOKEN", "salla-replay-token")

        class FailedResponse:
            ok = False
            status_code = 503
            def json(self):
                return {"error": "temporary_provider_failure"}

        monkeypatch.setattr(
            "app.services.salla_connector_service.salla_connector_service.execute_update_order",
            lambda **kwargs: {"success": False, "status": "failed", "executed": True, "error": "provider_rejected_request", "provider_status": 503},
        )
        worker = GovernedWorker()
        first = worker.process_one(worker_id="salla-replay-failure-1", organization_id=org_id, job_id=job.id, plan_resolver=lambda payload: None)
        assert first["status"] == "failed"
        db.session.expire_all()
        job = db.session.get(AutomationQueueJob, job.id)
        assert job.status == "queued"
        assert job.attempts == 1
        job.available_at = datetime.utcnow()
        db.session.commit()
        second = worker.process_one(worker_id="salla-replay-failure-2", organization_id=org_id, job_id=job.id, plan_resolver=lambda payload: None)
        assert second["status"] == "blocked"
        db.session.expire_all()
        job = db.session.get(AutomationQueueJob, job.id)
        assert job.status == "dead_letter"
        assert job.workflow_state == "failed"
        assert job.attempts == 2

        replay = ControlledReplayService().replay(
            job_id=job.id, authorization=json.loads(job.payload_json)["authorization"], approver_id=1
        )
        assert replay["ok"] is True
        db.session.expire_all()
        replayed = db.session.get(AutomationQueueJob, job.id)
        replay_payload = json.loads(replayed.payload_json)
        assert replayed.status == "queued"
        assert replayed.job_key == job.job_key
        assert replayed.idempotency_key == job.idempotency_key
        assert replay_payload["execution_identity"]["execution_key"] == job.job_key
        assert replay_payload["execution_identity"]["idempotency_key"] == job.idempotency_key

        class SuccessResponse:
            ok = True
            status_code = 200
            def json(self):
                return {"data": {"id": "replayed-order", "updated": True}}

        monkeypatch.setattr(
            "app.services.salla_connector_service.salla_connector_service.execute_update_order",
            lambda **kwargs: {"success": True, "status": "completed", "executed": True, "provider_status": 200, "data": {"id": "replayed-order", "updated": True}},
        )
        success = worker.process_one(worker_id="salla-replay-success", organization_id=org_id, job_id=job.id, plan_resolver=lambda payload: None)
        assert success["status"] == "completed"
        assert success["executed"] is True
        db.session.expire_all()
        final_job = db.session.get(AutomationQueueJob, job.id)
        assert final_job.status == "completed"
        ledger = execution_ledger.get(organization_id=org_id, execution_key=job.job_key)
        assert ledger["status"] == "completed"
        evidence = execution_evidence.history(organization_id=org_id, execution_key=job.job_key)
        finished = [row for row in evidence if row["stage"] == "runtime.finished"]
        assert len(finished) == 1
        assert db.session.get(AutomationExecution, materialized["execution_id"]).status == "completed"

        duplicate = ControlledReplayService().replay(
            job_id=job.id, authorization=json.loads(final_job.payload_json)["authorization"], approver_id=1
        )
        assert duplicate["status"] == "not_dead_letter"

def test_replay_rejects_cross_tenant_authorization_context():
    from wsgi import application
    import json
    from app.core.execution.authorization import execution_authorization
    from app.models.automation_queue import AutomationQueueJob
    with application.app_context():
        queue = AutomationQueue()
        owner = Organization(name=f"ReplayOwner {uuid.uuid4().hex}", slug=f"replay-owner-{uuid.uuid4().hex}")
        attacker = Organization(name=f"ReplayAttacker {uuid.uuid4().hex}", slug=f"replay-attacker-{uuid.uuid4().hex}")
        db.session.add_all([owner, attacker])
        db.session.commit()
        plan = {"plan_id": f"cross-{uuid.uuid4().hex}", "action": "check_order", "organization_id": attacker.id}
        auth = execution_authorization.create_authorization(plan, approver_id=7)
        created = queue.enqueue({"organization_id": owner.id, "job_key": f"cross-{uuid.uuid4().hex}", "workflow_id": "wf-cross", "payload": {}})
        job = db.session.get(AutomationQueueJob, created["job_id"])
        job.status = "dead_letter"
        job.workflow_state = "failed"
        payload = {"execution_plan": plan, "authorization": auth, "action": "check_order"}
        job.payload_json = json.dumps(payload)
        db.session.commit()
        result = ControlledReplayService(queue).replay(job_id=job.id, authorization=auth, approver_id=7)
        assert result["status"] == "replay_tenant_mismatch"