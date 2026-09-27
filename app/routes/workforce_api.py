from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.workforce.registry import workforce_registry
from app.workforce.runtime import workforce_runtime
from app.services.corporate_force_card import corporate_force_card
from app.services.design_intelligence_reference import design_intelligence_reference


workforce_api_bp = Blueprint(
    "workforce_api",
    __name__,
    url_prefix="/api/workforce",
)


@workforce_api_bp.get("")
@login_required
def list_workforce():
    employees = workforce_registry.list()

    return jsonify({
        "success": True,
        "count": len(employees),
        "workforce": employees,
    })


@workforce_api_bp.get("/<workforce_id>")
@login_required
def get_workforce(workforce_id):
    employee = workforce_registry.get(
        workforce_id
    )

    if employee is None:
        return jsonify({
            "success": False,
            "error": "workforce_not_found",
        }), 404

    return jsonify({
        "success": True,
        "workforce": employee,
    })


@workforce_api_bp.get(
    "/industry/<industry_id>"
)
@login_required
def workforce_by_industry(industry_id):
    employees = workforce_registry.for_industry(
        industry_id
    )

    return jsonify({
        "success": True,
        "industry": industry_id,
        "count": len(employees),
        "workforce": employees,
    })


@workforce_api_bp.get(
    "/<workforce_id>/permissions"
)
@login_required
def workforce_permissions(workforce_id):
    employee = workforce_registry.get(
        workforce_id
    )

    if employee is None:
        return jsonify({
            "success": False,
            "error": "workforce_not_found",
        }), 404

    return jsonify({
        "success": True,
        "workforce_id": workforce_id,
        "allowed_actions": employee.get(
            "allowed_actions",
            [],
        ),
        "approval_actions": employee.get(
            "approval_actions",
            [],
        ),
        "capabilities": employee.get(
            "capabilities",
            [],
        ),
    })


@workforce_api_bp.post("/task")
@login_required
def create_workforce_task():
    payload = request.get_json(
        silent=True
    ) or {}

    workforce_id = payload.get(
        "workforce_id"
    )
    action = payload.get("action")
    data = payload.get("data") or {}

    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    result = workforce_runtime.create_task(
        workforce_id=workforce_id,
        action=action,
        organization_id=organization_id,
        data=data,
        user_id=current_user.id,
    )

    status_code = 200 if result.get(
        "success"
    ) else 422

    return jsonify(result), status_code


@workforce_api_bp.post("/task/<task_id>/execute")
@login_required
def execute_workforce_task(task_id):
    task = workforce_runtime.get_task(
        task_id
    )

    if task is None:
        return jsonify({
            "success": False,
            "status": "not_found",
            "error": "task_not_found",
        }), 404

    if task.get(
        "organization_id"
    ) != getattr(
        current_user,
        "organization_id",
        None,
    ):
        return jsonify({
            "success": False,
            "status": "blocked",
            "error": "tenant_security_violation",
        }), 403

    result = workforce_runtime.execute_task(
        task_id
    )

    status_code = 200 if result.get(
        "success"
    ) or result.get("status") == "waiting_approval" else 422

    return jsonify(result), status_code


@workforce_api_bp.post("/run")
@login_required
def run_workforce():
    payload = request.get_json(
        silent=True
    ) or {}

    workforce_id = payload.get(
        "workforce_id"
    )
    action = payload.get("action")
    data = payload.get("data") or {}

    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    result = workforce_runtime.run(
        workforce_id=workforce_id,
        action=action,
        organization_id=organization_id,
        data=data,
        user_id=current_user.id,
    )

    status_code = 200 if (
        result.get("success")
        or result.get("status")
        == "waiting_approval"
    ) else 422

    return jsonify(result), status_code


@workforce_api_bp.get("/tasks")
@login_required
def list_workforce_tasks():
    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    tasks = workforce_runtime.list_tasks(
        organization_id=organization_id
    )

    return jsonify({
        "success": True,
        "count": len(tasks),
        "tasks": tasks,
    })


from app.services.ai_team_control_plane import ai_team_control_plane


@workforce_api_bp.get("/team")
@login_required
def team_snapshot():
    organization_id = getattr(current_user, "organization_id", None)
    return jsonify(ai_team_control_plane.team_snapshot(organization_id))


@workforce_api_bp.post("/assignment/preview")
@login_required
def assignment_preview():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = ai_team_control_plane.assignment_preview(
        organization_id,
        payload.get("workforce_id"),
        payload.get("objective"),
        issue_id=payload.get("issue_id"),
        action=payload.get("action"),
    )
    return jsonify(result), 200 if result.get("status") != "BLOCKED" else 422


@workforce_api_bp.post("/mention/preview")
@login_required
def mention_preview():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = ai_team_control_plane.mention_preview(
        organization_id,
        payload.get("mention"),
        payload.get("objective"),
    )
    return jsonify(result)


@workforce_api_bp.post("/schedule/preview")
@login_required
def schedule_preview():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = ai_team_control_plane.schedule_preview(
        organization_id,
        payload.get("workforce_id"),
        payload.get("objective"),
        payload.get("schedule"),
    )
    return jsonify(result)


@workforce_api_bp.get("/corporate-force")
@login_required
def corporate_force_team_card():
    organization_id = getattr(current_user, "organization_id", None)
    return jsonify(corporate_force_card.build_team(organization_id))


@workforce_api_bp.get("/<workforce_id>/card")
@login_required
def corporate_force_member_card(workforce_id):
    organization_id = getattr(current_user, "organization_id", None)
    result = corporate_force_card.build(organization_id, workforce_id)
    return jsonify(result), 200 if result.get("status") != "BLOCKED" else 404


@workforce_api_bp.post("/design-intelligence/reference")
@login_required
def design_reference_evidence():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = design_intelligence_reference.build_reference_evidence(
        organization_id=organization_id,
        source_url=payload.get("source_url"),
        title=payload.get("title"),
        evidence_type=payload.get("evidence_type", "screen_reference"),
        macrostructure=payload.get("macrostructure"),
        design_tokens=payload.get("design_tokens"),
        observations=payload.get("observations"),
        provenance=payload.get("provenance"),
    )
    return jsonify(result), 200 if result.get("status") != "BLOCKED" else 422


@workforce_api_bp.post("/design-intelligence/contract")
@login_required
def design_contract_preview():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = design_intelligence_reference.build_design_contract(
        organization_id=organization_id,
        business_objective=payload.get("business_objective"),
        ux_constraints=payload.get("ux_constraints"),
        references=payload.get("references"),
        accessibility=payload.get("accessibility"),
    )
    return jsonify(result), 200 if result.get("status") != "BLOCKED" else 422


@workforce_api_bp.post("/design-intelligence/strategist/preview")
@login_required
def design_strategist_preview():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = design_intelligence_reference.strategist_preview(
        organization_id=organization_id,
        business_objective=payload.get("business_objective"),
        ux_constraints=payload.get("ux_constraints"),
        references=payload.get("references"),
    )
    return jsonify(result), 200 if result.get("status") != "BLOCKED" else 422


from app.services.opencode_engineering_control import opencode_engineering_control


@workforce_api_bp.get("/engineering/opencode")
@login_required
def opencode_engineering_catalog():
    return jsonify(opencode_engineering_control.role_catalog())


@workforce_api_bp.post("/engineering/opencode/plan")
@login_required
def opencode_engineering_plan():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = opencode_engineering_control.plan(payload.get("objective"), organization_id)
    return jsonify(result)


@workforce_api_bp.post("/engineering/opencode/assignment/preview")
@login_required
def opencode_engineering_assignment_preview():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = opencode_engineering_control.assignment_preview(
        payload.get("objective"), organization_id, payload.get("role")
    )
    return jsonify(result), 200 if result.get("status") != "BLOCKED" else 422

from app.services.durable_workforce_orchestration import durable_workforce_orchestration


@workforce_api_bp.get("/durable")
@login_required
def durable_workforce_tasks():
    organization_id = getattr(current_user, "organization_id", None)
    return jsonify({"success": True, "schema": durable_workforce_orchestration.SCHEMA,
                    "governance": durable_workforce_orchestration.GOVERNANCE,
                    "tasks": durable_workforce_orchestration.list_tasks(organization_id)})


@workforce_api_bp.post("/durable/assignments")
@login_required
def durable_create_assignment():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = durable_workforce_orchestration.create_assignment(
        organization_id, payload.get("workforce_id"), payload.get("objective"),
        idempotency_key=payload.get("idempotency_key"), created_by=current_user.id,
        parent_assignment_id=payload.get("parent_assignment_id"),
    )
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.post("/durable/tasks")
@login_required
def durable_create_task():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = durable_workforce_orchestration.create_task(
        organization_id, payload.get("assignment_id"), payload.get("action"),
        input_data=payload.get("input"), idempotency_key=payload.get("idempotency_key"),
    )
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.post("/durable/tasks/<int:task_id>/transition")
@login_required
def durable_transition_task(task_id):
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = durable_workforce_orchestration.transition(
        organization_id, task_id, payload.get("target"), actor=str(current_user.id),
        reason=payload.get("reason", "user_transition"), metadata=payload.get("metadata") or {},
    )
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.get("/durable/tasks/<int:task_id>")
@login_required
def durable_get_task(task_id):
    organization_id = getattr(current_user, "organization_id", None)
    task = durable_workforce_orchestration.task(organization_id, task_id)
    if not task:
        return jsonify({"success": False, "error": "task_not_found"}), 404
    return jsonify({"success": True, "task": task,
                    "history": durable_workforce_orchestration.history(organization_id, task_id)})


@workforce_api_bp.post("/durable/tasks/<int:task_id>/replay-preview")
@login_required
def durable_replay_preview(task_id):
    organization_id = getattr(current_user, "organization_id", None)
    return jsonify(durable_workforce_orchestration.replay_preview(organization_id, task_id))


@workforce_api_bp.post("/durable/tasks/<int:task_id>/recover")
@login_required
def durable_recover_task(task_id):
    organization_id = getattr(current_user, "organization_id", None)
    return jsonify(durable_workforce_orchestration.recover(organization_id, task_id, actor=str(current_user.id)))


@workforce_api_bp.post("/durable/schedules")
@login_required
def durable_schedule_assignment():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = durable_workforce_orchestration.schedule(
        organization_id, payload.get("assignment_id"), payload.get("schedule_key"),
        payload.get("schedule") or {},
    )
    return jsonify(result), 200 if result.get("success") else 422


from app.services.governed_workforce_orchestration import governed_workforce_orchestration
from app.services.corporate_force_card_v4 import corporate_force_card_v4


@workforce_api_bp.get("/orchestration")
@login_required
def governed_orchestration_snapshot():
    organization_id = getattr(current_user, "organization_id", None)
    return jsonify(governed_workforce_orchestration.orchestration_snapshot(organization_id))


@workforce_api_bp.post("/orchestration/select")
@login_required
def governed_orchestration_select():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = governed_workforce_orchestration.select(
        organization_id, objective=payload.get("objective"), action=payload.get("action"),
        role=payload.get("role"), capability=payload.get("capability"),
    )
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.post("/orchestration/delegate")
@login_required
def governed_orchestration_delegate():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = governed_workforce_orchestration.delegate(
        organization_id, payload.get("parent_assignment_id"), payload.get("workforce_id"),
        payload.get("objective"), idempotency_key=payload.get("idempotency_key"),
        created_by=current_user.id,
    )
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.post("/orchestration/dag")
@login_required
def governed_orchestration_dag():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = governed_workforce_orchestration.create_dag_tasks(
        organization_id, payload.get("assignment_id"), payload.get("tasks") or [],
    )
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.get("/orchestration/tasks/<int:task_id>/readiness")
@login_required
def governed_orchestration_readiness(task_id):
    organization_id = getattr(current_user, "organization_id", None)
    return jsonify(governed_workforce_orchestration.readiness(organization_id, task_id))


@workforce_api_bp.post("/orchestration/approval-bundle")
@login_required
def governed_orchestration_approval_bundle():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = governed_workforce_orchestration.approval_bundle(
        organization_id, payload.get("assignment_id"), payload.get("task_ids") or [],
    )
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.post("/orchestration/approval-validate")
@login_required
def governed_orchestration_approval_validate():
    payload = request.get_json(silent=True) or {}
    organization_id = getattr(current_user, "organization_id", None)
    result = governed_workforce_orchestration.validate_approval(
        organization_id, payload.get("assignment_id"), payload.get("approval") or {},
    )
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.post("/orchestration/schedules/<int:schedule_id>/reconcile")
@login_required
def governed_orchestration_schedule_reconcile(schedule_id):
    organization_id = getattr(current_user, "organization_id", None)
    result = governed_workforce_orchestration.schedule_next(organization_id, schedule_id)
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.post("/orchestration/tasks/<int:task_id>/recovery-preview")
@login_required
def governed_orchestration_recovery_preview(task_id):
    organization_id = getattr(current_user, "organization_id", None)
    return jsonify(governed_workforce_orchestration.recovery_preview(organization_id, task_id))


@workforce_api_bp.get("/corporate-force-v4")
@login_required
def corporate_force_team_card_v4():
    organization_id = getattr(current_user, "organization_id", None)
    return jsonify(corporate_force_card_v4.build_team(organization_id))


@workforce_api_bp.get("/<workforce_id>/card-v4")
@login_required
def corporate_force_member_card_v4(workforce_id):
    organization_id = getattr(current_user, "organization_id", None)
    result = corporate_force_card_v4.build(organization_id, workforce_id)
    return jsonify(result), 200 if result.get("status") != "BLOCKED" else 404


from app.services.workforce_outcome_learning import workforce_outcome_learning


@workforce_api_bp.get("/outcome-learning/recommend")
@login_required
def workforce_outcome_learning_recommend():
    organization_id = getattr(current_user, "organization_id", None)
    payload = request.args
    result = workforce_outcome_learning.recommend(
        organization_id, objective=payload.get("objective", ""), action=payload.get("action"),
        capability=payload.get("capability"), role=payload.get("role"),
    )
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.get("/outcome-learning/snapshot")
@login_required
def workforce_outcome_learning_snapshot():
    organization_id = getattr(current_user, "organization_id", None)
    result = workforce_outcome_learning.learning_snapshot(
        organization_id, action=request.args.get("action"), period=request.args.get("period", "30d")
    )
    return jsonify(result), 200 if result.get("success") else 422


from app.services.mendes.mendes_outcome_pilot import mendes_outcome_pilot_service


@workforce_api_bp.get("/mendes/outcome-pilot")
@login_required
def mendes_outcome_pilot():
    organization_id = getattr(current_user, "organization_id", None)
    result = mendes_outcome_pilot_service.prepare(organization_id)
    return jsonify(result), 200 if result.get("success") else 422


@workforce_api_bp.post("/mendes/outcome-pilot/evaluate")
@login_required
def mendes_outcome_pilot_evaluate():
    organization_id = getattr(current_user, "organization_id", None)
    payload = request.get_json(silent=True) or {}
    result = mendes_outcome_pilot_service.evaluate_authoritative_outcome(
        organization_id, payload.get("packet") or {}, payload.get("results") or {}
    )
    return jsonify(result), 200 if result.get("success") else 422
