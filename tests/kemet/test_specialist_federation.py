import pytest
from app.core.federation.federated_specialist_router import FederatedSpecialistRouter
from app.core.federation.manus_adapter import ManusAdapter
from app.core.federation.specialist_contracts import SpecialistRequest

def test_specialist_router_requires_verified_connection():
    with pytest.raises(LookupError):
        FederatedSpecialistRouter().decide({"agentic"}, preferred="manus")

def test_manus_adapter_requires_governed_authorization(monkeypatch):
    monkeypatch.setenv("MANUS_API_KEY", "test-key")
    with pytest.raises(PermissionError):
        ManusAdapter().submit(SpecialistRequest(1, "task-1", "research"))

def test_manus_submission_is_private_and_async(monkeypatch):
    monkeypatch.setenv("MANUS_API_KEY", "test-key")
    class Response:
        ok = True
        def json(self):
            return {"ok": True, "task_id": f"manus-{unique_id}", "request_id": "req-1"}
    def fake_post(*args, **kwargs):
        assert kwargs["json"]["share_visibility"] == "private"
        assert kwargs["headers"]["x-manus-api-key"] == "test-key"
        return Response()
    monkeypatch.setattr("app.core.federation.manus_adapter.governed_request", fake_post)
    monkeypatch.setenv("KEMET_EXECUTION_SECRET", "unit-test-secret")
    from app.core.execution.authorization import ExecutionAuthorizationService
    service = ExecutionAuthorizationService()
    from app.core.execution.authorization import execution_authorization
    execution_authorization.secret = "unit-test-secret"
    from wsgi import application
    from app import db
    with application.app_context():
        db.create_all()
        import uuid
        unique_id = uuid.uuid4().hex
        plan = {"plan_id": "plan-1", "organization_id": 7, "action": "manus.task.create", "execution_key": f"exec-manus-{unique_id}"}
        authorization = service.create_authorization(plan, approver_id=42)
        result = ManusAdapter().submit(
            SpecialistRequest(7, "task-1", "research"), plan=plan, authorization=authorization
        )
    assert result.status == "submitted"
    assert result.external_task_id == f"manus-{unique_id}"




def test_manus_duplicate_execution_reuses_durable_receipt(monkeypatch):
    monkeypatch.setenv("MANUS_API_KEY", "test-key")
    monkeypatch.setenv("KEMET_EXECUTION_SECRET", "unit-test-secret")
    from wsgi import application
    from app import db
    from app.core.execution.authorization import ExecutionAuthorizationService, execution_authorization
    with application.app_context():
        db.create_all()
        execution_authorization.secret = "unit-test-secret"
        import uuid
        plan = {"plan_id": "plan-reuse", "organization_id": 8, "action": "manus.task.create", "execution_key": f"exec-reuse-{uuid.uuid4().hex}"}
        auth = ExecutionAuthorizationService().create_authorization(plan, approver_id=42)
        calls = {"count": 0}
        class Response:
            ok = True
            def json(self):
                return {"ok": True, "task_id": f"manus-reuse-{plan['execution_key']}", "request_id": "req-reuse"}
        def fake_post(*args, **kwargs):
            calls["count"] += 1
            return Response()
        monkeypatch.setattr("app.core.federation.manus_adapter.governed_request", fake_post)
        adapter = ManusAdapter()
        first = adapter.submit(SpecialistRequest(8, "task-reuse", "research"), plan=plan, authorization=auth)
        second = adapter.submit(SpecialistRequest(8, "task-reuse", "research"), plan=plan, authorization=auth)
        assert first.external_task_id == second.external_task_id == f"manus-reuse-{plan['execution_key']}"
        assert calls["count"] == 1


def test_manus_denied_submission_does_not_reserve_execution_key(monkeypatch):
    monkeypatch.setenv("MANUS_API_KEY", "test-key")
    from wsgi import application
    from app import db
    from app.core.execution.authorization import ExecutionAuthorizationService, execution_authorization
    import uuid
    with application.app_context():
        db.create_all()
        execution_authorization.secret = "unit-test-secret"
        key = f"exec-denied-{uuid.uuid4().hex}"
        plan = {"plan_id": "plan-denied", "organization_id": 9, "action": "manus.task.create", "execution_key": key}
        auth = ExecutionAuthorizationService().create_authorization(plan, approver_id=42)
        auth["token"] = "tampered"
        try:
            ManusAdapter().submit(SpecialistRequest(9, "task-denied", "research"), plan=plan, authorization=auth)
        except PermissionError:
            pass
        from app.models.external_task import ExternalTaskRecord
        assert ExternalTaskRecord.query.filter_by(organization_id=9, execution_key=key, action="manus.task.create").first() is None
