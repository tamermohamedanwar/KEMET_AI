from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user

from app import db
from app.services.kpi_service import KPIService
from app.services.bos_intelligence import BOSIntelligenceService
from app.models import (
    AIUsage,
    Ticket,
    Document,
    Subscription,
)


dashboard = Blueprint('dashboard', __name__)

try:
    from app.models import Organization
except ImportError:
    Organization = None


def _current_organization_id():
    return getattr(current_user, "organization_id", None)


def _current_usage(organization_id):
    if not organization_id:
        return 0, 100

    from datetime import datetime

    month = datetime.utcnow().strftime("%Y-%m")

    usage = (
        AIUsage.query
        .filter_by(
            organization_id=organization_id,
            month=month
        )
        .first()
    )

    used = usage.requests if usage else 0

    subscription = (
        Subscription.query
        .filter_by(
            organization_id=organization_id
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )

    plan = subscription.plan.lower() if subscription and subscription.plan else "free"

    limits = {
        "free": 100,
        "starter": 1000,
        "business": 5000,
        "enterprise": 50000,
    }

    limit = limits.get(plan, 100)

    return used, limit


def _current_plan(organization_id):
    if not organization_id:
        return "free"

    subscription = (
        Subscription.query
        .filter_by(
            organization_id=organization_id
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )

    if not subscription:
        return "free"

    if getattr(subscription, "status", None) not in (None, "active", "paid"):
        return "free"

    return subscription.plan or "free"


@dashboard.route('/dashboard/api/kpis')
@login_required
def kpis():
    organization_id = _current_organization_id()

    period = request.args.get("period", "30d")

    if period not in KPIService.PERIODS:
        return jsonify({
            "success": False,
            "error": "Invalid period",
            "allowed_periods": list(KPIService.PERIODS.keys()),
        }), 400

    try:
        data = KPIService.get_kpis(
            organization_id=organization_id,
            period=period,
        )

        return jsonify({
            "success": True,
            "organization_id": organization_id,
            "data": data,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500


@dashboard.route('/dashboard')
@login_required
def index():
    organization_id = _current_organization_id()

    ai_used, ai_limit = _current_usage(organization_id)

    ai_remaining = max(ai_limit - ai_used, 0)

    usage_percent = 0

    if ai_limit:
        usage_percent = min(
            round((ai_used / ai_limit) * 100),
            100
        )

    open_tickets = 0

    if organization_id:
        open_tickets = (
            Ticket.query
            .filter(
                Ticket.organization_id == organization_id,
                Ticket.status.in_(["open", "pending"])
            )
            .count()
        )

    document_query = Document.query

    if organization_id is not None:
        document_query = document_query.filter(
            Document.organization_id == organization_id
        )

    document_count = document_query.count()

    plan_name = _current_plan(organization_id)

    return render_template(
        "admin/dashboard.html",
        stats={},
        ai_used=ai_used,
        ai_limit=ai_limit,
        ai_remaining=ai_remaining,
        usage_percent=usage_percent,
        open_tickets=open_tickets,
        document_count=document_count,
        plan_name=plan_name,
    )




@dashboard.route('/dashboard/api/bos/actions')
@login_required
def bos_actions():
    organization_id = _current_organization_id()

    try:
        brief = BOSIntelligenceService.get_brief(
            organization_id=organization_id
        )

        actions = brief.get("priority_actions", [])

        normalized = []

        for index, item in enumerate(actions[:12], start=1):
            if not isinstance(item, dict):
                continue

            decision_id = (
                item.get("decision_id")
                or item.get("id")
            )

            normalized.append({
                "id": decision_id,
                "decision_id": decision_id,
                "type": item.get("type", "signal"),
                "priority": item.get("priority", "low"),
                "title": item.get("title", "Business action"),
                "message": item.get("message", ""),
                "recommended_action": item.get(
                    "recommended_action",
                    "Review this business signal."
                ),
            })

        return jsonify({
            "success": True,
            "organization_id": organization_id,
            "health_score": brief.get("health_score", 0),
            "summary": brief.get("summary", ""),
            "actions": normalized,
            "counts": brief.get("counts", {}),
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500

@dashboard.route('/dashboard/api/bos')
@login_required
def bos_intelligence():
    organization_id = _current_organization_id()

    try:
        data = BOSIntelligenceService.get_brief(
            organization_id=organization_id
        )

        return jsonify(data)

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500


@dashboard.route('/dashboard/api/bos/decisions')
@login_required
def bos_decisions():
    organization_id = _current_organization_id()

    try:
        data = BOSIntelligenceService.get_decisions(
            organization_id=organization_id,
            limit=10,
        )

        return jsonify(data)

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500


@dashboard.route('/dashboard/api/bos/decision-summary')
@login_required
def bos_decision_summary():
    organization_id = _current_organization_id()

    try:
        data = BOSIntelligenceService.get_decision_summary(
            organization_id=organization_id,
            limit=10,
        )

        return jsonify(data)

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500

@dashboard.route("/dashboard/api/bos/executive-snapshot")
@login_required
def bos_executive_snapshot():
    organization_id = _current_organization_id()

    try:
        data = BOSIntelligenceService.get_executive_snapshot(
            organization_id=organization_id,
            limit=10,
        )

        return jsonify(data)

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500

@dashboard.route("/dashboard/api/bos/governance")
@login_required
def bos_governance():
    organization_id = _current_organization_id()

    try:
        data = BOSIntelligenceService.get_governance_options(
            organization_id=organization_id,
            limit=10,
        )

        return jsonify(data)

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500

@dashboard.route("/dashboard/api/bos/approval-preview/<decision_id>")
@login_required
def bos_approval_preview(decision_id):
    organization_id = _current_organization_id()

    try:
        data = BOSIntelligenceService.build_approval_preview(
            organization_id=organization_id,
            decision_id=decision_id,
        )

        if not data.get("success"):
            return jsonify(data), 404

        return jsonify(data)

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500


@dashboard.route("/dashboard/api/bos/decision-transition", methods=["POST"])
@login_required
def bos_decision_transition():
    """
    Apply a BOS governance transition.

    Approve uses the canonical BOS approval bridge and therefore
    reaches AutomationApprovalService, cryptographic authorization,
    the execution boundary, and the central execution gate.
    Reject never executes.
    Snooze remains advisory.
    """
    organization_id = _current_organization_id()
    user_id = getattr(current_user, "id", None)

    if not organization_id:
        return jsonify({
            "ok": False,
            "message": "No organization is assigned to this account.",
        }), 403

    payload = request.get_json(silent=True) or {}
    decision_id = str(payload.get("decision_id") or "").strip()
    transition = str(
        payload.get("transition") or ""
    ).strip().lower()

    if not decision_id:
        return jsonify({
            "ok": False,
            "message": "decision_id is required.",
        }), 400

    if transition not in {"approve", "reject", "snooze"}:
        return jsonify({
            "ok": False,
            "message": "Unsupported transition.",
        }), 400

    preview = BOSIntelligenceService.build_approval_preview(
        organization_id=organization_id,
        decision_id=decision_id,
    )

    if not preview.get("success"):
        return jsonify({
            "ok": False,
            "message": "Decision not found.",
        }), 404

    decision = preview.get("decision") or {}

    if transition == "approve":
        action = str(
            decision.get("action")
            or decision.get("executable_action")
            or ""
        ).strip().lower()

        if not action:
            return jsonify({
                "ok": False,
                "error": "approval_requires_explicit_action",
                "decision_id": decision_id,
            }), 422

        from app.automation.orchestrator import orchestrator
        from app.services.bos_approval_service import (
            bos_approval_service,
        )

        allowed_actions = getattr(
            orchestrator,
            "ALLOWED_ACTIONS",
            set(),
        )

        if action not in allowed_actions:
            return jsonify({
                "ok": False,
                "error": "action_not_allowed",
                "decision_id": decision_id,
                "action": action,
            }), 422

        command_map = {
            "lead_scoring": "Find my hottest leads",
            "churn_detection": "Find customers at risk of churn",
            "revenue_opportunity": "Find revenue opportunities",
            "customer_retention": "Retain customers at risk",
            "ai_sales_qualification": "Qualify sales leads",
            "payment_issue": "Review payment issues",
            "account_help": "Review account issues",
            "sales_follow_up": "Follow up with customers",
            "order_tracking": "Track order",
            "create_ticket": "Create support ticket",
            "smart_ticket_ai": "Review support tickets",
            "send_notification": "Send business notification",
            "refund_request": "Process refund request",
        }

        command = str(
            decision.get("command")
            or decision.get("executable_command")
            or command_map.get(action)
            or ""
        ).strip()

        if not command:
            return jsonify({
                "ok": False,
                "error": "no_safe_execution_command",
                "decision_id": decision_id,
                "action": action,
            }), 422

        try:
            plan = orchestrator.understand(command)

            if plan.action != action:
                return jsonify({
                    "ok": False,
                    "error": "action_command_mismatch",
                    "decision_id": decision_id,
                    "expected_action": action,
                    "resolved_action": plan.action,
                }), 422

            prepared = bos_approval_service.prepare(
                organization_id=organization_id,
                action_type=action,
                reason=(
                    decision.get("reason")
                    or decision.get("recommended_action")
                    or "Approved BOS business decision."
                ),
                data={
                    "command": command,
                    "decision_id": decision_id,
                    "organization_id": organization_id,
                    "user_id": user_id,
                    **dict(plan.parameters or {}),
                },
                requested_by=user_id,
            )

            if not prepared.get("success"):
                return jsonify({
                    "ok": False,
                    "decision_id": decision_id,
                    "action": action,
                    "approval": prepared,
                }), 422

            approval_id = prepared.get("approval_id")

            approved = bos_approval_service.approve(
                approval_id=approval_id,
                decided_by=user_id,
            )

            return jsonify({
                "ok": bool(approved.get("success")),
                "decision_id": decision_id,
                "action": action,
                "approval": approved,
                "execution": approved.get("execution"),
            }), (
                200
                if approved.get("success")
                else 422
            )

        except Exception as exc:
            return jsonify({
                "ok": False,
                "error": "governed_execution_error",
                "message": str(exc),
                "decision_id": decision_id,
                "action": action,
            }), 500

    result = BOSIntelligenceService.get_approval_transition(
        preview,
        transition,
    )

    return jsonify({
        "ok": True,
        "decision_id": decision_id,
        "transition": transition,
        "result": result,
    })


@dashboard.route("/dashboard/api/bos/decision-approve", methods=["POST"])
@login_required
def bos_decision_approve_execute():
    """
    Convert an approved BOS decision into the governed orchestration path.
    Only explicit registered actions may be executed.
    Human-readable recommendations are never executed as commands.
    """
    organization_id = _current_organization_id()
    user_id = getattr(current_user, "id", None)

    if not organization_id:
        return jsonify({
            "ok": False,
            "message": "No organization is assigned to this account.",
        }), 403

    payload = request.get_json(silent=True) or {}
    decision_id = str(payload.get("decision_id") or "").strip()

    if not decision_id:
        return jsonify({
            "ok": False,
            "message": "decision_id is required.",
        }), 400

    preview = BOSIntelligenceService.build_approval_preview(
        organization_id=organization_id,
        decision_id=decision_id,
    )

    if not preview.get("success"):
        return jsonify(preview), 404

    decision = preview.get("decision") or {}

    action = str(
        decision.get("action")
        or decision.get("executable_action")
        or ""
    ).strip().lower()

    command = str(
        decision.get("command")
        or decision.get("executable_command")
        or ""
    ).strip()

    from app.automation.orchestrator import orchestrator

    allowed_actions = getattr(
        orchestrator,
        "ALLOWED_ACTIONS",
        set(),
    )

    if not action:
        return jsonify({
            "ok": False,
            "error": "approval_requires_explicit_action",
            "message": (
                "This decision contains only a human-readable "
                "recommendation and has no explicit executable action."
            ),
            "decision_id": decision_id,
        }), 422

    if action not in allowed_actions:
        return jsonify({
            "ok": False,
            "error": "action_not_allowed",
            "message": "The decision action is not allowed by the Orchestrator.",
            "decision_id": decision_id,
            "action": action,
        }), 422

    if command:
        execution_command = command
    else:
        command_map = {
            "lead_scoring": "Find my hottest leads",
            "churn_detection": "Find customers at risk of churn",
            "revenue_opportunity": "Find revenue opportunities",
            "customer_retention": "Retain customers at risk",
            "ai_sales_qualification": "Qualify sales leads",
            "payment_issue": "Review payment issues",
            "account_help": "Review account issues",
            "sales_follow_up": "Follow up with customers",
            "order_tracking": "Track order",
            "create_ticket": "Create support ticket",
            "smart_ticket_ai": "Review support tickets",
            "send_notification": "Send business notification",
            "refund_request": "Process refund request",
        }

        execution_command = command_map.get(action)

    if not execution_command:
        return jsonify({
            "ok": False,
            "error": "no_safe_execution_command",
            "message": "No safe executable command is mapped to this action.",
            "decision_id": decision_id,
            "action": action,
        }), 422

    try:
        plan = orchestrator.understand(execution_command)
        if plan.action != action:
            return jsonify({
                "ok": False,
                "error": "action_command_mismatch",
                "message": "The executable command does not resolve to the approved action.",
                "decision_id": decision_id,
                "expected_action": action,
                "resolved_action": plan.action,
            }), 422

        result = orchestrator.execute(
            execution_command,
            organization_id=organization_id,
            user_id=user_id,
        )
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": "orchestrator_error",
            "message": str(exc),
        }), 500

    return jsonify({
        "ok": True,
        "decision_id": decision_id,
        "action": action,
        "approval": {
            "approved": True,
            "human_approved": True,
        },
        "orchestration": result,
    })


@dashboard.route("/dashboard/api/bos/control-center")
@login_required
def bos_control_center():
    organization_id = _current_organization_id()

    try:
        snapshot = BOSIntelligenceService.get_executive_snapshot(
            organization_id=organization_id,
        )

        governance = BOSIntelligenceService.get_governance_options(
            organization_id=organization_id,
            limit=10,
        )

        return jsonify({
            "success": True,
            "organization_id": organization_id,
            "health_score": snapshot.get("health_score", 0),
            "focus": snapshot.get("focus", ""),
            "counts": snapshot.get("counts", {}),
            "top_decisions": snapshot.get("top_decisions", []),
            "governance": governance.get(
                "governance",
                {},
            ),
            "mode": "advisory",
            "approval_required": True,
            "external_execution": False,
            "database_mutation": False,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500

# V5.14_ENTITLEMENT_OVERVIEW_API
@dashboard.route("/dashboard/api/entitlement")
@login_required
def entitlement_overview():
    organization_id = _current_organization_id()

    try:
        from app.services.entitlement_service import EntitlementService

        data = EntitlementService.overview(
            organization_id=organization_id,
        )

        return jsonify(data)

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500


@dashboard.route("/dashboard/api/bos/decision-lifecycle")
@login_required
def bos_decision_lifecycle():
    """Return a read-only lifecycle projection for BOS decisions."""
    organization_id = _current_organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 403

    try:
        from app.services.decision_lifecycle import DecisionLifecycleService

        period = request.args.get("period", "30d")
        data = BOSIntelligenceService.get_decisions(
            organization_id=organization_id,
            limit=10,
        )
        result = DecisionLifecycleService.project(
            organization_id,
            data.get("decisions", []),
            period=period,
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "decision_lifecycle_unavailable",
            "message": str(exc),
        }), 500


@dashboard.route("/dashboard/api/bos/learning-loop")
@login_required
def bos_learning_loop():
    """Return read-only evaluation and learning signals for BOS decisions."""
    organization_id = _current_organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 403

    try:
        from app.services.decision_lifecycle import DecisionLifecycleService
        from app.services.evaluation_learning import EvaluationLearningService

        period = request.args.get("period", "30d")
        data = BOSIntelligenceService.get_decisions(
            organization_id=organization_id,
            limit=10,
        )
        lifecycle = DecisionLifecycleService.project(
            organization_id,
            data.get("decisions", []),
            period=period,
        )
        return jsonify(EvaluationLearningService.build(lifecycle.get("items", [])))
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "learning_loop_unavailable",
            "message": str(exc),
        }), 500


@dashboard.route("/dashboard/api/federation/observability")
@login_required
def federation_observability():
    """Return a tenant-safe, read-only federation health snapshot."""
    try:
        from app.core.provider_observability import provider_observability
        organization_id = _current_organization_id()
        snapshot = provider_observability.snapshot(organization_id)
        return jsonify({
            "success": True,
            "mode": "read_only",
            "approval_required": True,
            "external_execution": False,
            "database_mutation": False,
            **snapshot,
        })
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }), 500
