import json

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.admin.decorators import admin_required
from app.models.automation import (
    AutomationWorkflow,
    AutomationAction,
    AutomationExecution,
    AutomationApproval,
)
from app.automation.engine import AutomationEngine
from app.services.automation_approval_service import automation_approval_service

admin_automation_bp = Blueprint(
    "admin_automation",
    __name__,
    url_prefix="/admin/automation",
)




@admin_automation_bp.route("/toggle/<int:workflow_id>", methods=["POST"])
@admin_required
def toggle_automation(workflow_id):
    organization_id = current_user.organization_id

    workflow = (
        AutomationWorkflow.query
        .filter_by(
            id=workflow_id,
            organization_id=organization_id,
        )
        .first()
    )

    if workflow is None:
        flash("Automation not found.", "error")
        return redirect(
            url_for("admin_automation.automation_dashboard")
        )

    workflow.is_active = not workflow.is_active
    db.session.commit()

    status = "activated" if workflow.is_active else "paused"

    flash(
        f"{workflow.name} {status}.",
        "success",
    )

    return redirect(
        url_for("admin_automation.automation_dashboard")
    )



# ============================================================
# KEMET AI APPROVAL CENTER
# ============================================================

@admin_automation_bp.route("/approvals")
@admin_required
def automation_approvals():
    organization_id = current_user.organization_id

    approvals = (
        AutomationApproval.query
        .filter_by(organization_id=organization_id)
        .order_by(AutomationApproval.id.desc())
        .all()
    )

    pending_count = sum(
        1 for approval in approvals
        if approval.status == "pending"
    )

    approved_count = sum(
        1 for approval in approvals
        if approval.status == "approved"
    )

    rejected_count = sum(
        1 for approval in approvals
        if approval.status == "rejected"
    )

    return render_template(
        "admin/automation_approvals.html",
        approvals=approvals,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
    )


@admin_automation_bp.route(
    "/approvals/<int:approval_id>",
    methods=["GET"],
)
@admin_required
def automation_approval_detail(approval_id):
    organization_id = current_user.organization_id

    approval = (
        AutomationApproval.query
        .filter_by(
            id=approval_id,
            organization_id=organization_id,
        )
        .first()
    )

    if approval is None:
        flash("Approval request not found.", "error")
        return redirect(
            url_for("admin_automation.automation_approvals")
        )

    request_data = {}

    if approval.request_json:
        try:
            request_data = json.loads(approval.request_json)
        except Exception:
            request_data = {
                "raw": approval.request_json
            }

    decision_data = {}

    if approval.decision_json:
        try:
            decision_data = json.loads(approval.decision_json)
        except Exception:
            decision_data = {
                "raw": approval.decision_json
            }

    return render_template(
        "admin/automation_approval_detail.html",
        approval=approval,
        request_data=request_data,
        decision_data=decision_data,
    )


@admin_automation_bp.route(
    "/approvals/<int:approval_id>/approve",
    methods=["POST"],
)
@admin_required
def approve_automation_approval(approval_id):
    organization_id = current_user.organization_id

    approval = (
        AutomationApproval.query
        .filter_by(
            id=approval_id,
            organization_id=organization_id,
        )
        .first()
    )

    if approval is None:
        flash("Approval request not found.", "error")
        return redirect(
            url_for("admin_automation.automation_approvals")
        )

    if approval.status != "pending":
        flash(
            f"Approval is already {approval.status}.",
            "error",
        )
        return redirect(
            url_for(
                "admin_automation.automation_approval_detail",
                approval_id=approval.id,
            )
        )

    result = automation_approval_service.approve(
        approval.id,
        decided_by=current_user.id,
    )

    if result.get("success"):
        flash(
            "Approval granted successfully.",
            "success",
        )
    else:
        flash(
            result.get("message", "Approval failed."),
            "error",
        )

    return redirect(
        url_for(
            "admin_automation.automation_approval_detail",
            approval_id=approval.id,
        )
    )


@admin_automation_bp.route(
    "/approvals/<int:approval_id>/reject",
    methods=["POST"],
)
@admin_required
def reject_automation_approval(approval_id):
    organization_id = current_user.organization_id

    approval = (
        AutomationApproval.query
        .filter_by(
            id=approval_id,
            organization_id=organization_id,
        )
        .first()
    )

    if approval is None:
        flash("Approval request not found.", "error")
        return redirect(
            url_for("admin_automation.automation_approvals")
        )

    if approval.status != "pending":
        flash(
            f"Approval is already {approval.status}.",
            "error",
        )
        return redirect(
            url_for(
                "admin_automation.automation_approval_detail",
                approval_id=approval.id,
            )
        )

    reason = (
        request.form.get("reason") or
        "Rejected by administrator."
    ).strip()

    result = automation_approval_service.reject(
        approval.id,
        decided_by=current_user.id,
        reason=reason,
    )

    if result.get("success"):
        flash(
            "Approval rejected.",
            "success",
        )
    else:
        flash(
            result.get("message", "Rejection failed."),
            "error",
        )

    return redirect(
        url_for(
            "admin_automation.automation_approval_detail",
            approval_id=approval.id,
        )
    )


@admin_automation_bp.route("/dashboard")
@admin_required
def automation_dashboard():
    organization_id = current_user.organization_id

    workflows = (
        AutomationWorkflow.query
        .filter_by(organization_id=organization_id)
        .order_by(AutomationWorkflow.id.desc())
        .all()
    )

    executions = (
        AutomationExecution.query
        .join(
            AutomationWorkflow,
            AutomationExecution.workflow_id == AutomationWorkflow.id,
        )
        .filter(
            AutomationWorkflow.organization_id == organization_id
        )
        .all()
    )

    total = len(executions)
    successful = sum(
        1 for e in executions if e.status == "completed"
    )
    failed = sum(
        1 for e in executions if e.status == "failed"
    )

    active = sum(
        1 for w in workflows if w.is_active
    )

    # Automation usage for the current organization.
    usage = total

    plan_limits = {
        "free": 100,
        "starter": 1000,
        "business": 5000,
        "enterprise": 50000,
    }

    try:
        from app.services.ai_usage_service import get_plan
        current_plan = get_plan(organization_id)

        if isinstance(current_plan, dict):
            current_plan = current_plan.get("plan", "free")
    except Exception:
        current_plan = "free"

    usage_limit = plan_limits.get(current_plan, 100)
    usage_remaining = max(usage_limit - usage, 0)

    return render_template(
        "admin/automation_dashboard.html",
        workflows=workflows,
        total=total,
        successful=successful,
        failed=failed,
        active=active,
        current_plan=current_plan,
        automation_usage=usage,
        usage_limit=usage_limit,
        usage_remaining=usage_remaining,
    )

@admin_automation_bp.route("/analytics")
@admin_required
def automation_analytics():
    organization_id = current_user.organization_id

    executions = (
        AutomationExecution.query
        .join(
            AutomationWorkflow,
            AutomationExecution.workflow_id == AutomationWorkflow.id,
        )
        .filter(
            AutomationWorkflow.organization_id == organization_id
        )
        .order_by(AutomationExecution.id.desc())
        .all()
    )

    total = len(executions)
    successful = sum(
        1 for e in executions
        if e.status == "completed"
    )
    failed = sum(
        1 for e in executions
        if e.status == "failed"
    )

    workflows = (
        AutomationWorkflow.query
        .filter_by(organization_id=organization_id)
        .all()
    )

    workflow_stats = []

    for workflow in workflows:
        items = [
            e for e in executions
            if e.workflow_id == workflow.id
        ]

        workflow_stats.append({
            "id": workflow.id,
            "name": workflow.name,
            "total": len(items),
            "successful": sum(
                1 for e in items
                if e.status == "completed"
            ),
            "failed": sum(
                1 for e in items
                if e.status == "failed"
            ),
        })

    success_rate = (
        round((successful / total) * 100, 1)
        if total else 0
    )

    return render_template(
        "admin/automation_analytics.html",
        total=total,
        successful=successful,
        failed=failed,
        success_rate=success_rate,
        workflow_stats=workflow_stats,
    )





# ============================================================
# KEMET AI AUTOMATION MARKETPLACE
# ============================================================


@admin_automation_bp.route("/automation-marketplace/install/<string:key>", methods=["POST"])
@admin_required
def install_marketplace_automation(key):
    organization_id = current_user.organization_id

    template = next(
        (item for item in MARKETPLACE_AUTOMATIONS if item["key"] == key),
        None,
    )

    if template is None:
        flash("Automation template not found.", "error")
        return redirect(url_for("admin_automation.automation_templates"))

    plan_order = {
        "free": 0,
        "starter": 1,
        "business": 2,
        "enterprise": 3,
    }

    current_plan = get_plan(organization_id)
    if isinstance(current_plan, dict):
        current_plan = current_plan.get("plan", "free")

    required_plan = template["plan"]

    if plan_order.get(current_plan, 0) < plan_order.get(required_plan, 0):
        flash(
            f"This automation requires the {required_plan} plan.",
            "error",
        )
        return redirect(url_for("admin_automation.automation_templates"))

    existing = (
        AutomationWorkflow.query
        .filter_by(
            organization_id=organization_id,
            name=template["name"],
        )
        .first()
    )

    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.session.commit()

        flash("Automation is already installed.", "info")
        return redirect(url_for("admin_automation.automation_templates"))

    workflow = AutomationWorkflow(
        name=template["name"],
        organization_id=organization_id,
        trigger_type=template["trigger"],
        is_active=True,
    )

    db.session.add(workflow)
    db.session.flush()

    action = AutomationAction(
        workflow_id=workflow.id,
        position=1,
        action_type=template["action"],
        is_active=True,
    )

    db.session.add(action)
    db.session.commit()

    flash(
        f"{template['name']} installed successfully.",
        "success",
    )

    return redirect(url_for("admin_automation.automation_templates"))


MARKETPLACE_AUTOMATIONS = [
    {
        "key": "smart_ticket",
        "name": "Smart Ticket AI",
        "description": "Automatically classify and organize customer tickets with AI.",
        "plan": "free",
        "trigger": "ticket_message_created",
        "action": "smart_ticket_ai",
    },
    {
        "key": "ai_customer_support",
        "name": "AI Customer Support",
        "description": "Generate automatic AI replies to customer support messages.",
        "plan": "starter",
        "trigger": "ticket_message_created",
        "action": "generate_ai_reply",
    },
    {
        "key": "order_tracking",
        "name": "AI Order Tracking",
        "description": "Automatically detect order questions and return shipment status.",
        "plan": "business",
        "trigger": "ticket_message_created",
        "action": "generate_ai_reply",
    },
    {
        "key": "business_notifications",
        "name": "Business Notifications",
        "description": "Automatically send internal business notifications.",
        "plan": "business",
        "trigger": "ticket_message_created",
        "action": "send_notification",
    },
]

@admin_automation_bp.route("/")
@admin_required
def index():
    organization_id = getattr(current_user, "organization_id", None)

    if not organization_id:
        flash("No organization assigned to this account.", "error")
        return redirect(url_for("main.dashboard"))

    workflows = (
        AutomationWorkflow.query
        .filter_by(organization_id=organization_id)
        .order_by(AutomationWorkflow.id.desc())
        .all()
    )

    executions = (
        AutomationExecution.query
        .join(
            AutomationWorkflow,
            AutomationExecution.workflow_id == AutomationWorkflow.id,
        )
        .filter(
            AutomationWorkflow.organization_id == organization_id
        )
        .order_by(AutomationExecution.id.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "admin/automation.html",
        workflows=workflows,
        executions=executions,
    )



@admin_automation_bp.route("/create", methods=["POST"])
@admin_required
def create():
    organization_id = getattr(current_user, "organization_id", None)

    if not organization_id:
        flash("No organization assigned to this account.", "error")
        return redirect(url_for("admin_automation.index"))

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    trigger_type = (request.form.get("trigger_type") or "ticket_created").strip()
    action_type = (request.form.get("action_type") or "").strip()

    if not name:
        flash("Workflow name is required.", "error")
        return redirect(url_for("admin_automation.index"))

    allowed_actions = {
        "create_ticket",
        "check_order",
        "generate_ai_reply",
        "smart_ticket_ai",
        "send_notification",
    }

    if action_type not in allowed_actions:
        flash("Invalid automation action.", "error")
        return redirect(url_for("admin_automation.index"))

    workflow = AutomationWorkflow(
        organization_id=organization_id,
        name=name,
        description=description,
        trigger_type=trigger_type,
        is_active=True,
    )

    db.session.add(workflow)
    db.session.flush()

    config = {}

    if action_type == "check_order":
        config = {
            "order_id": request.form.get("order_id", "").strip()
        }

    elif action_type == "send_notification":
        config = {
            "title": request.form.get("notification_title", "").strip(),
            "message": request.form.get("notification_message", "").strip(),
        }

    elif action_type == "generate_ai_reply":
        config = {
            "message": request.form.get("message", "").strip(),
        }

    action = AutomationAction(
        workflow_id=workflow.id,
        position=1,
        action_type=action_type,
        config_json=json.dumps(
            config,
            ensure_ascii=False,
        ),
        is_active=True,
    )

    db.session.add(action)
    db.session.commit()

    flash("Automation workflow created successfully.", "success")
    return redirect(
        url_for(
            "admin_automation.edit",
            workflow_id=workflow.id,
        )
    )



@admin_automation_bp.route(
    "/template/<template_type>",
    methods=["POST"]
)
@admin_required
def use_template(template_type):
    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    if not organization_id:
        flash(
            "No organization assigned to this account.",
            "error",
        )
        return redirect(
            url_for("admin_automation.index")
        )

    templates = {
        "ai_customer_support": {
            "name": "AI Customer Support",
            "description": (
                "AI-powered customer support with "
                "automatic order-status handling."
            ),
        },
        "order_tracking": {
            "name": "Order Tracking",
            "description": (
                "Automatically identify order requests "
                "and return the latest order status."
            ),
        },
        "smart_ticket": {
            "name": "Smart Ticket",
            "description": (
                "Automatically create and route support "
                "tickets from customer messages."
            ),
        },
        "business_notification": {
            "name": "Business Notification",
            "description": (
                "Automatically notify the business when "
                "important customer events occur."
            ),
        },
    }

    template = templates.get(template_type)

    if not template:
        flash(
            "Invalid automation template.",
            "error",
        )
        return redirect(
            url_for("admin_automation.index")
        )

    source = (
        AutomationWorkflow.query
        .filter_by(
            name=template["name"],
            is_active=True,
        )
        .order_by(AutomationWorkflow.id.asc())
        .first()
    )

    if not source:
        flash(
            "Automation template is unavailable.",
            "error",
        )
        return redirect(
            url_for("admin_automation.index")
        )

    workflow = AutomationWorkflow(
        organization_id=organization_id,
        name=template["name"],
        description=template["description"],
        trigger_type=source.trigger_type,
        is_active=False,
    )

    db.session.add(workflow)
    db.session.flush()

    source_actions = (
        AutomationAction.query
        .filter_by(workflow_id=source.id)
        .order_by(AutomationAction.position.asc())
        .all()
    )

    for source_action in source_actions:
        action = AutomationAction(
            workflow_id=workflow.id,
            action_type=source_action.action_type,
            position=source_action.position,
            is_active=source_action.is_active,
            config_json=source_action.config_json,
        )
        db.session.add(action)

    db.session.commit()

    flash(
        f"{workflow.name} installed successfully.",
        "success",
    )

    return redirect(
        url_for(
            "admin_automation.edit",
            workflow_id=workflow.id,
        )
    )


@admin_automation_bp.route("/<int:workflow_id>/executions")
@admin_required
def execution_history(workflow_id):
    organization_id = getattr(current_user, "organization_id", None)

    workflow = (
        AutomationWorkflow.query
        .filter_by(
            id=workflow_id,
            organization_id=organization_id,
        )
        .first_or_404()
    )

    executions = (
        AutomationExecution.query
        .filter_by(workflow_id=workflow.id)
        .order_by(AutomationExecution.id.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "admin/automation_executions.html",
        workflow=workflow,
        executions=executions,
    )


@admin_automation_bp.route(
    "/<int:workflow_id>/executions/<int:execution_id>"
)
@admin_required
def execution_detail(workflow_id, execution_id):
    organization_id = getattr(current_user, "organization_id", None)

    workflow = (
        AutomationWorkflow.query
        .filter_by(
            id=workflow_id,
            organization_id=organization_id,
        )
        .first_or_404()
    )

    execution = (
        AutomationExecution.query
        .filter_by(
            id=execution_id,
            workflow_id=workflow.id,
        )
        .first_or_404()
    )

    output = []

    if execution.output_json:
        try:
            output = json.loads(execution.output_json)
        except Exception:
            output = []

    action_results = output if isinstance(output, list) else []

    return render_template(
        "admin/automation_execution_detail.html",
        workflow=workflow,
        execution=execution,
        output=output,
        action_results=action_results,
    )


@admin_automation_bp.route("/<int:workflow_id>/run", methods=["POST"])
@admin_required
def run(workflow_id):
    organization_id = getattr(current_user, "organization_id", None)

    workflow = (
        AutomationWorkflow.query
        .filter_by(
            id=workflow_id,
            organization_id=organization_id,
        )
        .first_or_404()
    )

    data = {
        "user_id": current_user.id,
        "message": request.form.get(
            "message",
            "Manual Kemet AI automation test",
        ),
        "order_id": request.form.get(
            "order_id",
            "KEMET-MANUAL-TEST",
        ),
    }

    result = AutomationEngine().execute(
        event=workflow.trigger_type,
        data=data,
        organization_id=organization_id,
        workflow_id=workflow.id,
    )

    if not result:
        flash("No matching automation execution occurred.", "error")
    else:
        statuses = [item.get("status") for item in result if isinstance(item, dict)]

        if any(status == "failed" for status in statuses):
            flash("Automation execution failed. Check Execution History.", "error")
        elif any(status == "blocked" for status in statuses):
            flash("Automation blocked by the current usage limit.", "warning")
        elif any(status == "completed" for status in statuses):
            flash("Automation executed successfully.", "success")
        else:
            flash("Automation returned no completed execution.", "warning")

    return redirect(url_for("admin_automation.index"))


# KEMET-AUTOMATION-MARKET-V2

@admin_automation_bp.route(
    "/<int:workflow_id>/edit",
    methods=["GET", "POST"],
)
@admin_required
def edit(workflow_id):

    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    workflow = (
        AutomationWorkflow.query
        .filter_by(
            id=workflow_id,
            organization_id=organization_id,
        )
        .first_or_404()
    )

    action = (
        AutomationAction.query
        .filter_by(
            workflow_id=workflow.id,
        )
        .order_by(
            AutomationAction.position.asc()
        )
        .first()
    )

    if request.method == "POST":

        workflow.name = (
            request.form.get("name") or workflow.name
        ).strip()

        workflow.description = (
            request.form.get("description") or ""
        ).strip()

        workflow.trigger_type = (
            request.form.get(
                "trigger_type"
            )
            or workflow.trigger_type
        ).strip()

        if action:

            action.action_type = (
                request.form.get(
                    "action_type"
                )
                or action.action_type
            ).strip()

            config = {}

            if action.action_type == "generate_ai_reply":
                config = {
                    "message": (
                        request.form.get("message")
                        or ""
                    ).strip()
                }

            elif action.action_type == "check_order":
                config = {
                    "order_id": (
                        request.form.get("order_id")
                        or ""
                    ).strip()
                }

            elif action.action_type == "create_ticket":
                config = {
                    "title": (
                        request.form.get("ticket_title")
                        or ""
                    ).strip()
                }

            elif action.action_type == "send_notification":
                config = {
                    "title": (
                        request.form.get("notification_title")
                        or ""
                    ).strip(),
                    "message": (
                        request.form.get("notification_message")
                        or ""
                    ).strip(),
                }

            action.config_json = json.dumps(
                config,
                ensure_ascii=False,
            )

        db.session.commit()

        flash(
            "Workflow updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "admin_automation.edit",
                workflow_id=workflow.id,
            )
        )

    config = {}

    if action and action.config_json:
        try:
            config = json.loads(action.config_json)
        except Exception:
            config = {}

    return render_template(
        "admin/automation_edit.html",
        workflow=workflow,
        action=action,
        config=config,
    )


# ============================================================
# Kemet AI - Automation Builder
# ============================================================

@admin_automation_bp.route("/builder", methods=["GET", "POST"])
@admin_required
def automation_builder():
    organization_id = getattr(current_user, "organization_id", None)

    if not organization_id:
        flash("Organization is required.", "error")
        return redirect(url_for("admin.index"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        trigger_type = (request.form.get("trigger_type") or "").strip()
        action_type = (request.form.get("action_type") or "").strip()

        if not name or not trigger_type or not action_type:
            flash("All automation fields are required.", "error")
            return redirect(url_for("admin_automation.automation_builder"))

        workflow = AutomationWorkflow(
            name=name,
            organization_id=organization_id,
            trigger_type=trigger_type,
            is_active=True,
        )

        db.session.add(workflow)
        db.session.flush()

        condition = (request.form.get("condition") or "").strip()

        config = {}
        if condition:
            config["condition"] = condition

        action = AutomationAction(
            workflow_id=workflow.id,
            position=1,
            action_type=action_type,
            config_json=json.dumps(config, ensure_ascii=False),
            is_active=True,
        )

        db.session.add(action)
        db.session.commit()

        flash("Automation created successfully.", "success")
        return redirect(url_for("admin_automation.automation_builder"))

    workflows = (
        AutomationWorkflow.query
        .filter_by(
            organization_id=organization_id,
            is_active=True,
        )
        .order_by(AutomationWorkflow.id.asc())
        .all()
    )

    return render_template(
        "admin/automation_builder.html",
        workflows=workflows,
    )

# ============================================================
# Kemet AI - Automation Templates
# ============================================================

AUTOMATION_TEMPLATES = {
    "ai_customer_support": {
        "name": "AI Customer Support",
        "plan": "free",
        "trigger_type": "ticket_message_created",
        "action_type": "generate_ai_reply",
        "condition": "support",
    },
    "order_tracking": {
        "name": "Order Tracking",
        "plan": "starter",
        "trigger_type": "ticket_message_created",
        "action_type": "generate_ai_reply",
        "condition": "order",
    },
    "smart_ticket": {
        "name": "Smart Ticket",
        "plan": "free",
        "trigger_type": "ticket_message_created",
        "action_type": "smart_ticket_ai",
        "condition": "support",
    },
    "business_notification": {
        "name": "Business Notification",
        "plan": "starter",
        "trigger_type": "ticket_message_created",
        "action_type": "send_notification",
        "condition": "notification",
    },
    "payment_followup": {
        "name": "Payment Follow-up",
        "plan": "business",
        "trigger_type": "payment_received",
        "action_type": "send_notification",
        "condition": "payment",
    },
}


@admin_automation_bp.route("/templates", methods=["GET"])
@admin_required
def automation_templates():
    current_plan = get_plan(organization_id)

    if isinstance(current_plan, dict):
        current_plan = current_plan.get("plan", "free")

    return render_template(
        "admin/automation_templates.html",
        templates=AUTOMATION_TEMPLATES,
        current_plan=current_plan,
    )


# ============================================================
# KEMET AI BOS — AI WORKFORCE CENTER
# ============================================================

@admin_automation_bp.route("/workforce")
@admin_required
def workforce_center():
    organization_id = current_user.organization_id

    workflows = (
        AutomationWorkflow.query
        .filter_by(organization_id=organization_id)
        .order_by(AutomationWorkflow.id.desc())
        .all()
    )

    executions = (
        AutomationExecution.query
        .join(
            AutomationWorkflow,
            AutomationExecution.workflow_id == AutomationWorkflow.id,
        )
        .filter(
            AutomationWorkflow.organization_id == organization_id
        )
        .order_by(AutomationExecution.id.desc())
        .all()
    )

    approvals = (
        AutomationApproval.query
        .filter_by(organization_id=organization_id)
        .order_by(AutomationApproval.id.desc())
        .all()
    )

    active_agents = sum(
        1 for workflow in workflows
        if workflow.is_active
    )

    completed = sum(
        1 for execution in executions
        if execution.status == "completed"
    )

    failed = sum(
        1 for execution in executions
        if execution.status == "failed"
    )

    running = sum(
        1 for execution in executions
        if execution.status == "running"
    )

    pending_approvals = sum(
        1 for approval in approvals
        if approval.status == "pending"
    )

    return render_template(
        "admin/workforce_center.html",
        workflows=workflows,
        executions=executions[:12],
        approvals=approvals[:8],
        active_agents=active_agents,
        completed=completed,
        failed=failed,
        running=running,
        pending_approvals=pending_approvals,
    )
