
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user

from app import db

from app.models.automation import (
    AutomationExecution,
    AutomationApproval,
    AutomationWorkflow,
    AutomationAction,
)
from app.models.ticket import Ticket
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.ai_usage import AIUsage
from app.models.audit import AuditRecord
from app.core.execution.governed_executor import governed_execution_service


command_center_bp = Blueprint(
    "command_center",
    __name__,
    url_prefix="/command-center",
)


def _organization_id():
    return getattr(current_user, "organization_id", None)


def _count(query):
    try:
        return query.count()
    except Exception:
        return 0


@command_center_bp.route("/")
@login_required
def index():
    return render_template(
        "command_center.html",
        user=current_user,
    )






@command_center_bp.route("/api/agent-policy/<int:action_id>")
@login_required
def agent_policy(action_id):
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": False,
            "error": "organization_required",
        }), 400

    try:
        action = (
            AutomationAction.query
            .join(AutomationWorkflow)
            .filter(
                AutomationAction.id == action_id,
                AutomationWorkflow.organization_id == organization_id,
            )
            .first()
        )

        if action is None:
            return jsonify({
                "success": False,
                "error": "action_not_found",
            }), 404

        approval_required = getattr(
            action,
            "requires_approval",
            False,
        )

        enabled = getattr(
            action,
            "enabled",
            True,
        )

        policy = {
            "action_id": action.id,
            "action_type": getattr(
                action,
                "action_type",
                None,
            ),
            "enabled": enabled,
            "approval_required": approval_required,
            "execution_mode": (
                "approval_required"
                if approval_required
                else "authorized_execution"
            ),
            "governance": {
                "organization_scoped": True,
                "authorization_required": True,
                "canonical_runtime": True,
            },
        }

        return jsonify({
            "success": True,
            "data": policy,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "agent_policy_unavailable",
            "message": str(exc),
        }), 500

@command_center_bp.route("/api/agent-capabilities")
@login_required
def agent_capabilities():
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": True,
            "data": [],
        })

    try:
        workflows = (
            AutomationWorkflow.query
            .filter_by(organization_id=organization_id)
            .order_by(AutomationWorkflow.id.asc())
            .all()
        )

        capabilities = []

        for workflow in workflows:
            for action in getattr(workflow, "actions", []) or []:
                capabilities.append({
                    "workflow_id": workflow.id,
                    "workflow_name": getattr(
                        workflow,
                        "name",
                        None,
                    ),
                    "action_id": getattr(
                        action,
                        "id",
                        None,
                    ),
                    "action_name": getattr(
                        action,
                        "name",
                        None,
                    ),
                    "action_type": getattr(
                        action,
                        "action_type",
                        None,
                    ),
                    "enabled": getattr(
                        action,
                        "enabled",
                        True,
                    ),
                    "approval_required": getattr(
                        action,
                        "requires_approval",
                        False,
                    ),
                })

        return jsonify({
            "success": True,
            "data": capabilities,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "agent_capabilities_unavailable",
            "message": str(exc),
        }), 500

@command_center_bp.route("/api/agents")
@login_required
def agents():
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": True,
            "data": [],
        })

    try:
        workflows = (
            AutomationWorkflow.query
            .filter_by(organization_id=organization_id)
            .order_by(AutomationWorkflow.id.asc())
            .all()
        )

        data = []

        for workflow in workflows:
            actions = []

            try:
                for action in getattr(workflow, "actions", []) or []:
                    actions.append({
                        "id": getattr(action, "id", None),
                        "name": getattr(action, "name", None),
                        "action_type": getattr(action, "action_type", None),
                    })
            except Exception:
                actions = []

            data.append({
                "id": workflow.id,
                "name": getattr(workflow, "name", None),
                "description": getattr(workflow, "description", None),
                "status": getattr(workflow, "status", None),
                "enabled": getattr(workflow, "enabled", True),
                "actions": actions,
            })

        return jsonify({
            "success": True,
            "data": data,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "agent_registry_unavailable",
            "message": str(exc),
        }), 500

@command_center_bp.route("/api/approvals")
@login_required
def approvals():
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": True,
            "data": [],
        })

    try:
        rows = (
            AutomationApproval.query
            .filter_by(organization_id=organization_id)
            .order_by(AutomationApproval.id.desc())
            .limit(50)
            .all()
        )

        data = []

        for row in rows:
            data.append({
                "id": row.id,
                "status": getattr(row, "status", None),
                "action": getattr(row, "action_type", None),
                "created_at": (
                    row.created_at.isoformat()
                    if getattr(row, "created_at", None)
                    else None
                ),
                "updated_at": (
                    row.updated_at.isoformat()
                    if getattr(row, "updated_at", None)
                    else None
                ),
            })

        return jsonify({
            "success": True,
            "data": data,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "approval_data_unavailable",
            "message": str(exc),
        }), 500

@command_center_bp.route("/api/governance")
@login_required
def governance():
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": True,
            "data": {
                "organization_id": None,
                "policies": [],
                "approvals": [],
                "executions": [],
                "audit": [],
            },
        })

    try:
        actions = (
            AutomationAction.query
            .join(AutomationWorkflow)
            .filter(
                AutomationWorkflow.organization_id == organization_id,
            )
            .order_by(AutomationAction.id.asc())
            .limit(50)
            .all()
        )

        approvals = (
            AutomationApproval.query
            .filter_by(organization_id=organization_id)
            .order_by(AutomationApproval.id.desc())
            .limit(20)
            .all()
        )

        executions = (
            AutomationExecution.query
            .join(AutomationWorkflow)
            .filter(
                AutomationWorkflow.organization_id == organization_id,
            )
            .order_by(AutomationExecution.id.desc())
            .limit(20)
            .all()
        )

        audit = (
            AuditRecord.query
            .filter_by(organization_id=organization_id)
            .order_by(AuditRecord.id.desc())
            .limit(30)
            .all()
        )

        return jsonify({
            "success": True,
            "data": {
                "organization_id": organization_id,
                "policies": [
                    {
                        "action_id": action.id,
                        "action_type": getattr(
                            action, "action_type", None
                        ),
                        "enabled": (
                            governed_execution_service._policy(
                                getattr(action, "action_type", "")
                            ) != "blocked"
                        ),
                        "approval_required": (
                            governed_execution_service._policy(
                                getattr(action, "action_type", "")
                            ) == "approval_required"
                        ),
                        "execution_mode": (
                            governed_execution_service._policy(
                                getattr(action, "action_type", "")
                            )
                        ),
                    }
                    for action in actions
                ],
                "approvals": [
                    {
                        "id": row.id,
                        "action": getattr(
                            row, "action_type", None
                        ),
                        "status": getattr(row, "status", None),
                        "created_at": (
                            row.created_at.isoformat()
                            if getattr(row, "created_at", None)
                            else None
                        ),
                    }
                    for row in approvals
                ],
                "executions": [
                    {
                        "id": row.id,
                        "workflow_id": getattr(
                            row, "workflow_id", None
                        ),
                        "status": getattr(row, "status", None),
                        "created_at": (
                            row.created_at.isoformat()
                            if getattr(row, "created_at", None)
                            else None
                        ),
                        "completed_at": (
                            row.completed_at.isoformat()
                            if getattr(row, "completed_at", None)
                            else None
                        ),
                    }
                    for row in executions
                ],
                "audit": [
                    {
                        "id": row.id,
                        "event_type": row.event_type,
                        "action": row.action,
                        "status": row.status,
                        "actor_type": row.actor_type,
                        "created_at": (
                            row.created_at.isoformat()
                            if row.created_at
                            else None
                        ),
                    }
                    for row in audit
                ],
            },
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "governance_data_unavailable",
            "message": str(exc),
        }), 500


@command_center_bp.route("/api/overview")
@login_required
def overview():
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": True,
            "data": {
                "active_agents": 0,
                "pending_approvals": 0,
                "automations": 0,
                "tickets": 0,
                "payments": 0,
                "subscriptions": 0,
                "ai_usage": 0,
                "organization_id": None,
            },
        })

    approval_query = AutomationApproval.query.filter_by(
        organization_id=organization_id
    )

    execution_query = AutomationExecution.query.filter_by(
        organization_id=organization_id
    )

    workflow_query = AutomationWorkflow.query.filter_by(
        organization_id=organization_id
    )

    ticket_query = Ticket.query.filter_by(
        organization_id=organization_id
    )

    payment_query = Payment.query.filter_by(
        organization_id=organization_id
    )

    subscription_query = Subscription.query.filter_by(
        organization_id=organization_id
    )

    usage_query = AIUsage.query.filter_by(
        organization_id=organization_id
    )

    pending_approvals = 0

    try:
        pending_approvals = _count(
            approval_query.filter(
                AutomationApproval.status == "waiting_approval"
            )
        )
    except Exception:
        try:
            pending_approvals = _count(
                approval_query.filter(
                    AutomationApproval.status == "pending"
                )
            )
        except Exception:
            pending_approvals = 0

    automations = _count(execution_query)

    try:
        automations = _count(
            execution_query.filter(
                AutomationExecution.status.in_([
                    "completed",
                    "running",
                    "waiting_approval",
                    "failed",
                ])
            )
        )
    except Exception:
        pass

    data = {
        "active_agents": 0,
        "pending_approvals": pending_approvals,
        "automations": automations,
        "tickets": _count(ticket_query),
        "payments": _count(payment_query),
        "subscriptions": _count(subscription_query),
        "ai_usage": _count(usage_query),
        "workflows": _count(workflow_query),
        "organization_id": organization_id,
    }

    return jsonify({
        "success": True,
        "data": data,
    })
