import hashlib
import hmac
import uuid
from uuid import uuid4

from app.services.salla_connector_service import SallaConnectorService


def test_salla_contract_and_plan_are_governed(monkeypatch):
    service = SallaConnectorService()
    monkeypatch.setattr(service, "register", lambda organization_id: {"registered": True})
    plan = service.plan_get_order(organization_id=7, order_id="123")
    assert plan["operation"] == "get_order"
    assert plan["governance"]["read_only"] is True
    assert plan["governance"]["auto_execute"] is False
    assert "/orders/123" in plan["endpoint"]


def test_salla_webhook_fails_closed_without_org_secret(monkeypatch):
    monkeypatch.delenv("KEMET_SALLA_ORG_7_WEBHOOK_SECRET", raising=False)
    assert SallaConnectorService.verify_webhook(organization_id=7, headers={"Authorization": "anything"}) is False


def test_salla_webhook_header_verification(monkeypatch):
    monkeypatch.setenv("KEMET_SALLA_WEBHOOK_HEADER", "X-Salla-Secret")
    monkeypatch.setenv("KEMET_SALLA_ORG_7_WEBHOOK_SECRET", "secret")
    assert SallaConnectorService.verify_webhook(organization_id=7, headers={"X-Salla-Secret": "secret"}) is True
    assert SallaConnectorService.verify_webhook(organization_id=7, headers={"X-Salla-Secret": "wrong"}) is False
    assert SallaConnectorService.verify_webhook(organization_id=8, headers={"X-Salla-Secret": "secret"}) is False


def test_salla_webhook_normalization_is_idempotent_and_non_executing():
    payload = {"event": "order.created", "data": {"id": "order-99", "status": "pending"}}
    first = SallaConnectorService.normalize_webhook(organization_id=7, payload=payload)
    second = SallaConnectorService.normalize_webhook(organization_id=7, payload=payload)
    assert first["idempotency_key"] == second["idempotency_key"]
    assert first["governance"]["queue_before_processing"] is True
    assert first["governance"]["external_execution"] is False


def test_salla_webhook_identity_is_required():
    try:
        SallaConnectorService.normalize_webhook(organization_id=7, payload={"event": "order.created", "data": {}})
    except ValueError as exc:
        assert str(exc) == "salla_webhook_identity_required"
    else:
        raise AssertionError("expected identity validation")


def test_salla_execution_disables_redirect_following(monkeypatch):
    service = SallaConnectorService()
    monkeypatch.setattr("app.services.salla_connector_service.resolve_secret", lambda *args, **kwargs: "secret")
    captured = {}
    class Response:
        ok = True
        status_code = 200
        def json(self):
            return {"data": {"id": "order-1"}}
    def fake_get(*args, **kwargs):
        captured.update(kwargs)
        return Response()
    monkeypatch.setattr("app.services.salla_connector_service.governed_request", fake_get)
    result = service.execute_get_order(organization_id=7, order_id="order-1")
    assert result["success"] is True
    assert captured["allow_redirects"] is False


def test_salla_webhook_materializes_governed_workflow_and_deduplicates(monkeypatch):
    from app import create_app, db
    from app.models.automation import AutomationApproval, AutomationExecution, AutomationWorkflow
    from app.models.automation_queue import AutomationQueueJob

    app = create_app()
    with app.app_context():
        event = SallaConnectorService.normalize_webhook(
            organization_id=1,
            payload={
                "event": "order.created",
                "data": {
                    "id": f"golden-order-1001-{uuid.uuid4().hex}",
                    "customer": {"id": 77, "name": "Golden Customer"},
                },
            },
        )
        result = SallaConnectorService.materialize_webhook_workflow(
            organization_id=1, event=event, requested_by=1
        )
        assert result["success"] is True
        assert result["status"] == "approval_required"
        assert result["workflow_id"]
        assert result["execution_id"]
        assert result["job_id"]
        assert result["approval_id"]

        workflow = db.session.get(AutomationWorkflow, result["workflow_id"])
        execution = db.session.get(AutomationExecution, result["execution_id"])
        approval = db.session.get(AutomationApproval, result["approval_id"])
        job = db.session.get(AutomationQueueJob, result["job_id"])
        assert workflow.organization_id == 1
        assert execution.workflow_id == workflow.id
        assert execution.status == "waiting_approval"
        assert approval.organization_id == 1
        assert approval.workflow_id == workflow.id
        assert approval.execution_id == execution.id
        assert approval.status == "pending"
        assert job.organization_id == 1
        assert job.execution_id == str(execution.id)
        assert job.workflow_id == str(workflow.id)
        assert job.workflow_state == "waiting_approval"

        duplicate = SallaConnectorService.materialize_webhook_workflow(
            organization_id=1, event=event, requested_by=1
        )
        assert duplicate["success"] is True
        assert duplicate["status"] == "deduplicated"
        assert duplicate["execution_id"] == execution.id


def test_salla_update_order_requires_canonical_authorization(monkeypatch):
    service = SallaConnectorService()
    blocked = service.execute_update_order(
        organization_id=1, order_id="100", updates={"customer": {"name": "x"}},
    )
    assert blocked["status"] == "blocked"
    assert blocked["error"] == "canonical_execution_required"


def test_salla_update_order_executes_only_through_governed_boundary(monkeypatch):
    service = SallaConnectorService()
    monkeypatch.setattr(
        "app.services.salla_connector_service.resolve_secret",
        lambda *args, **kwargs: "salla-token",
    )
    captured = {}

    class Response:
        ok = True
        status_code = 200
        def json(self):
            return {"data": {"id": "100", "updated": True}}

    def fake_request(*args, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("app.services.salla_connector_service.governed_request", fake_request)
    result = service.execute_update_order(
        organization_id=1,
        order_id="100",
        updates={"customer": {"name": "Kemet Customer"}},
        approved_execution=True,
        execution_authorization={"plan_hash": "a" * 64},
    )
    assert result["status"] == "completed"
    assert result["executed"] is True
    assert captured["allow_redirects"] is False
    assert captured["json"]["customer"]["name"] == "Kemet Customer"


def test_salla_golden_workflow_approval_worker_and_receipt(monkeypatch):
    from app import create_app, db
    from app.core.governed_worker import GovernedWorker
    from app.models.automation import AutomationApproval, AutomationExecution
    from app.models.automation_queue import AutomationQueueJob
    from app.services.automation_approval_service import automation_approval_service

    app = create_app()
    with app.app_context():
        event = SallaConnectorService.normalize_webhook(
            organization_id=3,
            payload={
                "event": "order.created",
                "data": {
                    "id": f"golden-order-2002-{uuid.uuid4().hex}",
                    "customer": {"id": 88, "name": "Approved Customer"},
                },
            },
        )
        materialized = SallaConnectorService.materialize_webhook_workflow(
            organization_id=3, event=event, requested_by=None
        )
        approval_id = materialized["approval_id"]
        execution_id = materialized["execution_id"]
        job_id = materialized["job_id"]

        approved = automation_approval_service.approve(approval_id, decided_by=1)
        assert approved["success"] is True
        assert approved["status"] == "approved"
        assert approved["execution"]["status"] == "queued"

        execution = db.session.get(AutomationExecution, execution_id)
        job = db.session.get(AutomationQueueJob, job_id)
        approval = db.session.get(AutomationApproval, approval_id)
        assert execution.status == "waiting_approval"
        assert approval.status == "approved"
        assert job.workflow_state == "queued"
        payload = __import__("json").loads(job.payload_json)
        assert payload["approval_id"] == approval_id
        assert payload["execution_identity"]["organization_id"] == 3
        assert payload["execution_identity"]["execution_id"] == str(execution_id)

        monkeypatch.setenv("KEMET_SALLA_ORG_3_ACCESS_TOKEN", "salla-token")

        class Response:
            ok = True
            status_code = 200
            def json(self):
                return {"data": {"id": f"golden-order-2002-{uuid.uuid4().hex}", "updated": True}}

        monkeypatch.setattr(
            "app.services.salla_connector_service.governed_request",
            lambda *args, **kwargs: Response(),
        )
        result = GovernedWorker().process_one(
            worker_id="salla-golden-worker",
            organization_id=3,
            job_id=job_id,
            plan_resolver=lambda payload: None,
        )
        assert result["status"] == "completed"
        assert result["executed"] is True
        assert result["detail"].get("success") is True

        db.session.expire_all()
        job = db.session.get(AutomationQueueJob, job_id)
        assert job.status == "completed"
        assert job.workflow_state == "completed"


def test_salla_worker_has_no_side_effect_before_approval(monkeypatch):
    from app import create_app, db
    from app.core.governed_worker import GovernedWorker

    app = create_app()
    with app.app_context():
        event = SallaConnectorService.normalize_webhook(
            organization_id=3,
            payload={"event": "order.created", "data": {"id": f"pending-{uuid.uuid4().hex}", "customer": {"name": "Pending"}}},
        )
        materialized = SallaConnectorService.materialize_webhook_workflow(
            organization_id=3, event=event, requested_by=None
        )
        called = []
        monkeypatch.setattr("app.services.salla_connector_service.governed_request", lambda *args, **kwargs: called.append(True))
        result = GovernedWorker().process_one(
            worker_id="salla-preapproval-worker", organization_id=3,
            job_id=materialized["job_id"], plan_resolver=lambda payload: None,
        )
        assert result["status"] == "idle"
        assert called == []


def test_salla_worker_blocks_tampered_execution_identity(monkeypatch):
    import json
    from app import create_app, db
    from app.core.governed_worker import GovernedWorker
    from app.models.automation_queue import AutomationQueueJob
    from app.services.automation_approval_service import automation_approval_service

    app = create_app()
    with app.app_context():
        event = SallaConnectorService.normalize_webhook(
            organization_id=3,
            payload={"event": "order.created", "data": {"id": f"tamper-{uuid.uuid4().hex}", "customer": {"name": "Tamper"}}},
        )
        materialized = SallaConnectorService.materialize_webhook_workflow(
            organization_id=3, event=event, requested_by=None
        )
        assert automation_approval_service.approve(materialized["approval_id"], decided_by=1)["success"] is True
        job = db.session.get(AutomationQueueJob, materialized["job_id"])
        payload = json.loads(job.payload_json)
        payload["execution_identity"]["execution_id"] = "tampered-execution"
        job.payload_json = json.dumps(payload)
        db.session.commit()
        called = []
        monkeypatch.setattr("app.services.salla_connector_service.governed_request", lambda *args, **kwargs: called.append(True))
        result = GovernedWorker().process_one(
            worker_id="salla-tamper-worker", organization_id=3,
            job_id=job.id, plan_resolver=lambda payload: None,
        )
        assert result["status"] == "blocked"
        assert result["detail"]["error"] == "execution_identity_mismatch:identity.execution_id"
        assert called == []
