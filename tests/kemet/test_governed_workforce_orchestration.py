from uuid import uuid4

from app import db
from app.models.durable_workforce import WorkforceAssignment, WorkforceTask, WorkforceTaskEvent
from app.services.durable_workforce_orchestration import durable_workforce_orchestration
from app.services.governed_workforce_orchestration import governed_workforce_orchestration
from wsgi import application


def _assignment(key, workforce="ai_sales_manager"):
    return durable_workforce_orchestration.create_assignment(
        1, workforce, "Phase 11 governed objective", idempotency_key=key, created_by=1
    )["assignment"]


def _cleanup(aid):
    task_ids = [row.id for row in db.session.query(WorkforceTask).filter_by(assignment_id=aid).all()]
    if task_ids:
        db.session.query(WorkforceTaskEvent).filter(WorkforceTaskEvent.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.session.query(WorkforceTask).filter_by(assignment_id=aid).delete()
    db.session.query(WorkforceAssignment).filter_by(id=aid).delete()
    db.session.commit()


def test_policy_selection_is_fail_closed_and_non_executing():
    with application.app_context():
        result = governed_workforce_orchestration.select(1, objective="qualify leads", action="lead_scoring")
        assert result["success"] is True
        assert result["execution"] is False
        blocked = governed_workforce_orchestration.select(1, objective="unsafe", action="unknown_action")
        assert blocked["status"] == "BLOCKED"


def test_delegation_is_tenant_scoped_and_cycle_safe():
    with application.app_context():
        parent = _assignment(f"phase11:{uuid4().hex}")
        child = governed_workforce_orchestration.delegate(
            1, parent["id"], "ai_lead_qualifier", "Qualify delegated leads",
            idempotency_key=f"phase11:{uuid4().hex}", created_by=1,
        )
        assert child["success"] is True
        assert child["assignment"]["delegation_parent_id"] == parent["id"]
        blocked = governed_workforce_orchestration.delegate(
            1, parent["id"], "ai_sales_manager", "Self delegation",
            idempotency_key=f"phase11:{uuid4().hex}", created_by=1,
        )
        assert blocked["status"] == "BLOCKED"
        _cleanup(child["assignment"]["id"])
        _cleanup(parent["id"])


def test_dag_rejects_cycles_and_creates_durable_tasks():
    with application.app_context():
        a = _assignment(f"phase11:{uuid4().hex}")
        bad = governed_workforce_orchestration.plan(1, a["id"], [
            {"id": "a", "action": "lead_scoring", "depends_on": ["b"]},
            {"id": "b", "action": "sales_follow_up", "depends_on": ["a"]},
        ])
        assert bad["status"] == "BLOCKED"
        good = governed_workforce_orchestration.create_dag_tasks(1, a["id"], [
            {"id": "a", "action": "lead_scoring"},
            {"id": "b", "action": "sales_follow_up", "depends_on": ["a"]},
        ])
        assert good["success"] is True
        assert len(good["tasks"]) == 2
        _cleanup(a["id"])


def test_dependency_readiness_blocks_until_dependency_completes():
    with application.app_context():
        a = _assignment(f"phase11:{uuid4().hex}")
        first = durable_workforce_orchestration.create_task(1, a["id"], "lead_scoring", idempotency_key=f"phase11:{uuid4().hex}")
        second = durable_workforce_orchestration.create_task(1, a["id"], "sales_follow_up", input_data={"depends_on": [first["task"]["id"]]}, idempotency_key=f"phase11:{uuid4().hex}")
        blocked = governed_workforce_orchestration.readiness(1, second["task"]["id"])
        assert blocked["status"] == "BLOCKED_BY_DEPENDENCY"
        assert governed_workforce_orchestration.readiness(1, first["task"]["id"])["status"] == "READY"
        _cleanup(a["id"])


def test_approval_bundle_is_bound_to_plan_and_permission_snapshot():
    with application.app_context():
        a = _assignment(f"phase11:{uuid4().hex}")
        plan = governed_workforce_orchestration.plan(1, a["id"], [{"id": "one", "action": "lead_scoring"}])
        assert plan["success"] is True
        task = durable_workforce_orchestration.create_task(1, a["id"], "lead_scoring", idempotency_key=f"phase11:{uuid4().hex}")["task"]
        bundle = governed_workforce_orchestration.approval_bundle(1, a["id"], [task["id"]])
        assert bundle["status"] == "APPROVAL_REQUIRED"
        valid = governed_workforce_orchestration.validate_approval(1, a["id"], bundle)
        assert valid["status"] == "APPROVAL_VALID"
        _cleanup(a["id"])


def test_recovery_preview_never_executes():
    with application.app_context():
        a = _assignment(f"phase11:{uuid4().hex}")
        task = durable_workforce_orchestration.create_task(1, a["id"], "lead_scoring", idempotency_key=f"phase11:{uuid4().hex}")["task"]
        durable_workforce_orchestration.transition(1, task["id"], "planned", actor="test", reason="plan")
        durable_workforce_orchestration.transition(1, task["id"], "approval_required", actor="test", reason="approval")
        durable_workforce_orchestration.transition(1, task["id"], "approved", actor="test", reason="approved", metadata={"approval_id": "a"})
        durable_workforce_orchestration.transition(1, task["id"], "queued", actor="test", reason="queue")
        durable_workforce_orchestration.transition(1, task["id"], "processing", actor="test", reason="start", metadata={"execution_key": "e"})
        durable_workforce_orchestration.transition(1, task["id"], "failed", actor="test", reason="timeout", metadata={"error": "timeout"})
        preview = governed_workforce_orchestration.recovery_preview(1, task["id"])
        assert preview["execution"] is False
        _cleanup(a["id"])


def test_routes_and_corporate_force_v4_are_governed():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    response = client.get("/api/workforce/orchestration")
    assert response.status_code == 200
    assert response.get_json()["governance"]["mcp"] is False
    response = client.get("/api/workforce/corporate-force-v4")
    assert response.status_code == 200
    assert response.get_json()["schema"] == "kemet.corporate_force_card.v4"
    assert response.get_json()["governance"]["execution_authority"] is False
