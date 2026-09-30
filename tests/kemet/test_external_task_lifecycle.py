import uuid

import pytest

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.external_task_lifecycle import (
    ExternalTaskLifecycleError,
    external_task_lifecycle,
)


def test_structured_metadata_is_retained_without_secret_keys():
    from app.core.external_task_lifecycle import ExternalTaskLifecycle
    clean = ExternalTaskLifecycle._safe_metadata({"result": {"summary": "ok", "token": "hidden"}, "items": [1, {"password": "hidden", "value": "kept"}]})
    assert clean["result"] == {"summary": "ok"}
    assert clean["items"] == [1, {"value": "kept"}]


def _org():
    uid = uuid.uuid4().hex
    row = Organization(name=f"External {uid}", slug=f"external-{uid}")
    db.session.add(row)
    db.session.commit()
    return row


def test_submission_is_durable_idempotent_and_secret_safe():
    with application.app_context():
        db.create_all()
        org = _org()
        uid = uuid.uuid4().hex
        first = external_task_lifecycle.create_submission(
            organization_id=org.id, provider_id="manus", external_task_id=f"m-{uid}",
            execution_key=f"exec-{uid}", plan_hash="plan-1", action="manus.task.create",
            request_id="req-1", metadata={"share_visibility": "private", "token": "secret"},
        )
        second = external_task_lifecycle.create_submission(
            organization_id=org.id, provider_id="manus", external_task_id=f"m-{uid}",
            execution_key=f"exec-{uid}", plan_hash="plan-1", action="manus.task.create",
        )
        assert first["id"] == second["id"]
        assert first["status"] == "submitted"
        assert "token" not in first["metadata"]
        assert first["external_task_id"] == f"m-{uid}"


def test_state_machine_and_reconciliation_are_idempotent():
    with application.app_context():
        db.create_all()
        org = _org()
        uid = uuid.uuid4().hex
        external_task_lifecycle.create_submission(
            organization_id=org.id, provider_id="manus", external_task_id=f"m-{uid}",
            execution_key=f"exec-{uid}", plan_hash="plan-2", action="manus.task.create",
        )
        running = external_task_lifecycle.update_state(
            organization_id=org.id, execution_key=f"exec-{uid}", status="running",
        )
        completed = external_task_lifecycle.update_state(
            organization_id=org.id, execution_key=f"exec-{uid}", status="completed",
        )
        again = external_task_lifecycle.update_state(
            organization_id=org.id, execution_key=f"exec-{uid}", status="completed",
        )
        assert running["status"] == "running"
        assert completed["status"] == "completed"
        assert again["status"] == "completed"


def test_invalid_transition_and_plan_mismatch_fail_closed():
    with application.app_context():
        db.create_all()
        org = _org()
        uid = uuid.uuid4().hex
        external_task_lifecycle.create_submission(
            organization_id=org.id, provider_id="manus", external_task_id=f"m-{uid}",
            execution_key=f"exec-{uid}", plan_hash="plan-3", action="manus.task.create",
        )
        with pytest.raises(ExternalTaskLifecycleError):
            external_task_lifecycle.update_state(
                organization_id=org.id, execution_key=f"exec-{uid}", status="completed",
            )
        with pytest.raises(ExternalTaskLifecycleError):
            external_task_lifecycle.update_state(
                organization_id=org.id, execution_key=f"exec-{uid}", status="running",
                plan_hash="wrong-plan",
            )


def test_ambiguous_state_is_terminal_and_cross_tenant_lookup_is_blocked():
    with application.app_context():
        db.create_all()
        first = _org()
        second = _org()
        uid = uuid.uuid4().hex
        external_task_lifecycle.create_submission(
            organization_id=first.id, provider_id="manus", external_task_id=f"m-{uid}",
            execution_key=f"exec-{uid}", plan_hash="plan-4", action="manus.task.create",
        )
        ambiguous = external_task_lifecycle.mark_ambiguous(
            organization_id=first.id, execution_key=f"exec-{uid}", reason="timeout_after_submit",
        )
        assert ambiguous["status"] == "ambiguous"
        with pytest.raises(ExternalTaskLifecycleError):
            external_task_lifecycle.update_state(
                organization_id=first.id, execution_key=f"exec-{uid}", status="running",
            )
        assert external_task_lifecycle.get(
            organization_id=second.id, execution_key=f"exec-{uid}"
        ) is None
