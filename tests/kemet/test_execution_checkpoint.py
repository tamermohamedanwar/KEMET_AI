import uuid

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.execution_checkpoint import execution_checkpoint


def _org(prefix):
    uid = uuid.uuid4().hex
    return Organization(name=f"{prefix} {uid}", slug=f"{prefix.lower()}-{uid}")


def test_checkpoint_completed_step_is_resume_safe():
    with application.app_context():
        db.create_all()
        org = _org("Checkpoint")
        db.session.add(org)
        db.session.commit()
        key = f"exec-{uuid.uuid4().hex}"
        first = execution_checkpoint.begin_step(
            organization_id=org.id, execution_key=key, plan_hash="hash-1",
            step_id="step-1", ordinal=0, worker_id="worker-a",
        )
        assert first["status"] == "started"
        execution_checkpoint.complete_step(
            organization_id=org.id, execution_key=key, plan_hash="hash-1",
            step_id="step-1", result={"success": True, "value": 42},
            worker_id="worker-a",
        )
        resumed = execution_checkpoint.begin_step(
            organization_id=org.id, execution_key=key, plan_hash="hash-1",
            step_id="step-1", ordinal=0, worker_id="worker-b",
        )
        assert resumed["status"] == "completed"
        assert resumed["checkpoint"]["result"]["value"] == 42


def test_checkpoint_ambiguous_state_fails_closed():
    with application.app_context():
        db.create_all()
        org = _org("Ambiguous")
        db.session.add(org)
        db.session.commit()
        key = f"exec-{uuid.uuid4().hex}"
        execution_checkpoint.begin_step(
            organization_id=org.id, execution_key=key, plan_hash="hash-1",
            step_id="step-1", ordinal=0, worker_id="worker-a",
        )
        retry = execution_checkpoint.begin_step(
            organization_id=org.id, execution_key=key, plan_hash="hash-1",
            step_id="step-1", ordinal=0, worker_id="worker-b",
        )
        assert retry["status"] == "ambiguous"


def test_checkpoint_rejects_plan_or_worker_mismatch_on_completion():
    with application.app_context():
        db.create_all()
        org = _org("Guard")
        db.session.add(org)
        db.session.commit()
        key = f"exec-{uuid.uuid4().hex}"
        execution_checkpoint.begin_step(
            organization_id=org.id, execution_key=key, plan_hash="hash-1",
            step_id="step-1", ordinal=0, worker_id="worker-a",
        )
        wrong_plan = execution_checkpoint.complete_step(
            organization_id=org.id, execution_key=key, plan_hash="hash-2",
            step_id="step-1", result={"success": True}, worker_id="worker-a",
        )
        assert wrong_plan["status"] == "plan_hash_mismatch"
        wrong_worker = execution_checkpoint.complete_step(
            organization_id=org.id, execution_key=key, plan_hash="hash-1",
            step_id="step-1", result={"success": True}, worker_id="worker-b",
        )
        assert wrong_worker["status"] == "worker_mismatch"
        saved = execution_checkpoint.history(organization_id=org.id, execution_key=key)
        assert saved[0]["status"] == "started"
