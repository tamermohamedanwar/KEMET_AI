import uuid

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.external_task_lifecycle import external_task_lifecycle
from app.core.federation.external_task_control_plane import external_task_control_plane
from app.core.federation.specialist_registry import specialist_registry


def _org():
    uid = uuid.uuid4().hex
    row = Organization(name=f"Control {uid}", slug=f"control-{uid}")
    db.session.add(row)
    db.session.commit()
    return row


def test_refresh_reconciles_provider_status_without_new_execution(monkeypatch):
    with application.app_context():
        db.create_all()
        org = _org()
        uid = uuid.uuid4().hex
        external_task_lifecycle.create_submission(
            organization_id=org.id, provider_id="manus", external_task_id=f"m-{uid}",
            execution_key=f"exec-{uid}", plan_hash="plan-1", action="manus.task.create",
        )

        class FakeAdapter:
            def inspect(self, *, external_task_id):
                assert external_task_id == f"m-{uid}"
                return {
                    "status": "stopped",
                    "metadata": {"task_url": "private"},
                    "result": {"summary": "completed result"},
                }

        monkeypatch.setattr(specialist_registry, "get", lambda provider_id: FakeAdapter())
        result = external_task_control_plane.get(
            organization_id=org.id, execution_key=f"exec-{uid}", refresh=True
        )
        assert result["status"] == "completed"
        assert result["metadata"]["task_url"] == "private"
        assert result["result"] == {"summary": "completed result"}
        assert result["evidence"]["execution_key"] == f"exec-{uid}"


def test_refresh_is_read_only_for_unknown_provider():
    with application.app_context():
        db.create_all()
        org = _org()
        uid = uuid.uuid4().hex
        external_task_lifecycle.create_submission(
            organization_id=org.id, provider_id="unknown", external_task_id=f"x-{uid}",
            execution_key=f"exec-{uid}", plan_hash="plan-2", action="external.create",
        )
        result = external_task_control_plane.get(
            organization_id=org.id, execution_key=f"exec-{uid}", refresh=True
        )
        assert result["status"] == "submitted"
