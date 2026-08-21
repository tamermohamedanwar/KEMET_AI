from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models.subscription import Subscription
from app.services.ai_usage_service import check_limit
from app.config.plans import PLAN_DETAILS as CENTRAL_PLAN_DETAILS

billing_bp = Blueprint("billing", __name__)


PLAN_DETAILS = CENTRAL_PLAN_DETAILS


@billing_bp.route("/billing")
@login_required
def billing():
    organization_id = current_user.organization_id

    usage = check_limit(organization_id)

    subscription = Subscription.query.filter_by(
        organization_id=organization_id
    ).first()

    current_plan = (
        subscription.plan.lower()
        if subscription and subscription.plan
        else "free"
    )

    subscription_status = (
        subscription.status.lower()
        if subscription and subscription.status
        else "active"
    )

    current_plan_details = PLAN_DETAILS.get(
        current_plan,
        PLAN_DETAILS["free"],
    )

    plans = []

    for plan_key in ("free", "starter", "business", "enterprise"):
        plan = PLAN_DETAILS[plan_key].copy()
        plan["key"] = plan_key
        plan["current"] = plan_key == current_plan
        plans.append(plan)

    return render_template(
        "billing.html",
        usage=usage,
        subscription=subscription,
        subscription_status=subscription_status,
        current_plan=current_plan,
        current_plan_details=current_plan_details,
        plans=plans,
    )
