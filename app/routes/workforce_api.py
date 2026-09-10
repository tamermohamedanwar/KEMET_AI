from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.workforce.registry import workforce_registry
from app.workforce.runtime import workforce_runtime


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
