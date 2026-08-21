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

            normalized.append({
                "id": index,
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

@dashboard.route("/dashboard/api/bos/approval-preview/<int:decision_id>")
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
