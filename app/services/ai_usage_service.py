from datetime import datetime
from app import db
from app.models.subscription import Subscription
from app.models.ai_usage import AIUsage


PLAN_LIMITS = {
    "free": 100,
    "starter": 1000,
    "business": 5000,
    "enterprise": 50000,
}


def current_month():
    return datetime.utcnow().strftime("%Y-%m")


def get_plan(organization_id):
    subscription = (
        Subscription.query
        .filter_by(
            organization_id=organization_id,
            status="active"
        )
        .first()
    )

    if not subscription:
        return "free", PLAN_LIMITS["free"], "inactive"

    plan = subscription.plan or "free"
    limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

    return plan, limit, subscription.status


def get_usage(organization_id):
    month = current_month()

    usage = (
        AIUsage.query
        .filter_by(
            organization_id=organization_id,
            month=month
        )
        .first()
    )

    if not usage:
        return {
            "month": month,
            "requests": 0,
            "tokens": 0,
        }

    return {
        "month": month,
        "requests": usage.requests or 0,
        "tokens": usage.tokens or 0,
    }


def check_limit(organization_id):
    plan, limit, status = get_plan(organization_id)
    usage = get_usage(organization_id)

    used = usage["requests"]
    remaining = max(limit - used, 0)

    return {
        "allowed": used < limit,
        "plan": plan,
        "status": status,
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "month": usage["month"],
    }


def record_usage(organization_id, tokens=0):
    month = current_month()

    usage = (
        AIUsage.query
        .filter_by(
            organization_id=organization_id,
            month=month
        )
        .first()
    )

    if not usage:
        usage = AIUsage(
            organization_id=organization_id,
            month=month,
            requests=0,
            tokens=0,
        )
        db.session.add(usage)

    usage.requests = (usage.requests or 0) + 1
    usage.tokens = (usage.tokens or 0) + int(tokens or 0)

    db.session.commit()

    return check_limit(organization_id)
