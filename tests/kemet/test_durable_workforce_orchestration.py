from uuid import uuid4

from app import db
from app.models.durable_workforce import WorkforceAssignment, WorkforceTask, WorkforceTaskEvent
from app.services.durable_workforce_orchestration import durable_workforce_orchestration
from wsgi import application


def test_durable_workforce_assignment_and_permission_snapshot():
    with application.app_context():
        key = f"phase10:{uuid4().hex}"
        result = durable_workforce_orchestration.create_assignment(
            1, "ai_sales_manager", "Qualify the next sales pipeline", idempotency_key=key, created_by=1
        )
        assert result["success"] is True
        assignment = result["assignment"]
        assert assignment["organization_id"] == 1
        assert assignment["permission_snapshot"]["role"] == "sales_manager"
        assert "lead_scoring" in assignment["permission_snapshot"]["allowed_actions"]
        db.session.query(WorkforceAssignment).filter_by(id=assignment["id"]).delete()
        db.session.commit()


def test_durable_task_lifecycle_requires_approval_and_evidence():
    with application.app_context():
        base = f"phase10:{uuid4().hex}"
        assignment_result = durable_workforce_orchestration.create_assignment(
            1, "ai_store_manager", "Handle a refund request", idempotency_key=f"{base}:a", created_by=1
        )
        aid = assignment_result["assignment"]["id"]
        task_result = durable_workforce_orchestration.create_task(
            1, aid, "refund_request", input_data={"order_id": "demo-1"}, idempotency_key=f"{base}:t"
        )
        tid = task_result["task"]["id"]
        assert task_result["task"]["permission_snapshot"]["approval_actions"] == ["refund_request"]
        assert durable_workforce_orchestration.transition(1, tid, "planned", actor="test", reason="plan")["success"]
        assert durable_workforce_orchestration.transition(1, tid, "approval_required", actor="test", reason="approval")["success"]
        blocked = durable_workforce_orchestration.transition(1, tid, "approved", actor="test", reason="missing")
        assert blocked["status"] == "BLOCKED"
        assert durable_workforce_orchestration.transition(1, tid, "approved", actor="test", reason="approved", metadata={"approval_id": "ap-1"})["success"]
        assert durable_workforce_orchestration.transition(1, tid, "queued", actor="test", reason="queue")["success"]
        assert durable_workforce_orchestration.transition(1, tid, "processing", actor="test", reason="start", metadata={"execution_key": "exec-phase10"})["success"]
        blocked = durable_workforce_orchestration.transition(1, tid, "executed", actor="test", reason="done", metadata={"execution_key": "exec-phase10"})
        assert blocked["status"] == "BLOCKED"
        assert durable_workforce_orchestration.transition(1, tid, "executed", actor="test", reason="done", metadata={"execution_key": "exec-phase10", "evidence_digest": "evidence-1"})["success"]
        assert durable_workforce_orchestration.transition(1, tid, "result_recorded", actor="test", reason="result", metadata={"result": {"qualified": True}})["success"]
        assert durable_workforce_orchestration.transition(1, tid, "measured", actor="test", reason="measure")["success"]
        learned = durable_workforce_orchestration.transition(1, tid, "learned", actor="test", reason="learn", metadata={"learning_digest": "learn-1"})
        assert learned["success"] is True
        assert len(durable_workforce_orchestration.history(1, tid)) == 10
        db.session.query(WorkforceTaskEvent).filter_by(task_id=tid).delete()
        db.session.query(WorkforceTask).filter_by(id=tid).delete()
        db.session.query(WorkforceAssignment).filter_by(id=aid).delete()
        db.session.commit()


def test_durable_idempotency_and_replay_are_non_executing():
    with application.app_context():
        base = f"phase10:{uuid4().hex}"
        assignment = durable_workforce_orchestration.create_assignment(1, "ai_sales_manager", "Recover a failed task", idempotency_key=f"{base}:a", created_by=1)["assignment"]
        first = durable_workforce_orchestration.create_task(1, assignment["id"], "lead_scoring", idempotency_key=f"{base}:t")
        second = durable_workforce_orchestration.create_task(1, assignment["id"], "lead_scoring", idempotency_key=f"{base}:t")
        assert second["status"] == "deduplicated"
        tid = first["task"]["id"]
        assert durable_workforce_orchestration.transition(1, tid, "planned", actor="test", reason="plan")["success"]
        assert durable_workforce_orchestration.transition(1, tid, "approval_required", actor="test", reason="approval")["success"]
        assert durable_workforce_orchestration.transition(1, tid, "approved", actor="test", reason="approved", metadata={"approval_id": "ap-2"})["success"]
        assert durable_workforce_orchestration.transition(1, tid, "queued", actor="test", reason="queue")["success"]
        assert durable_workforce_orchestration.transition(1, tid, "processing", actor="test", reason="start", metadata={"execution_key": "exec-fail"})["success"]
        assert durable_workforce_orchestration.transition(1, tid, "failed", actor="test", reason="provider_timeout", metadata={"error": "provider_timeout"})["success"]
        preview = durable_workforce_orchestration.replay_preview(1, tid)
        assert preview["status"] == "REPLAY_PREVIEW"
        assert preview["execution"] is False
        recovered = durable_workforce_orchestration.recover(1, tid)
        assert recovered["task"]["state"] == "retrying"
        assert recovered["task"]["attempt"] == 1
        db.session.query(WorkforceTaskEvent).filter_by(task_id=tid).delete()
        db.session.query(WorkforceTask).filter_by(id=tid).delete()
        db.session.query(WorkforceAssignment).filter_by(id=assignment["id"]).delete()
        db.session.commit()


def test_durable_routes_are_tenant_scoped_and_readable():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    response = client.get("/api/workforce/durable")
    assert response.status_code == 200
    body = response.get_json()
    assert body["schema"] == "kemet.durable_workforce_orchestration.v1"
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["mcp"] is False
