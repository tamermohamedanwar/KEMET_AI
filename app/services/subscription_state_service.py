"""Kemet AI authoritative subscription state resolver."""

from datetime import datetime, timezone


class SubscriptionStateService:
    """Resolve effective commercial state without mutating data."""

    ACTIVE_STATUSES = {"active", "trial", "trialing"}
    INACTIVE_STATUSES = {"inactive", "canceled", "cancelled", "suspended", "past_due", "unpaid"}

    @classmethod
    def resolve(cls, organization_id):
        from app.models import Subscription

        if not organization_id:
            return cls._state(None, "free", "missing_organization")

        subscription = (
            Subscription.query
            .filter_by(organization_id=organization_id)
            .first()
        )

        if not subscription:
            return cls._state(None, "free", "no_subscription")

        plan = str(getattr(subscription, "plan", None) or "free").strip().lower()
        status = str(getattr(subscription, "status", None) or "").strip().lower()

        if status in cls.ACTIVE_STATUSES:
            return cls._state(subscription, plan, "active")

        if status in cls.INACTIVE_STATUSES or status:
            return cls._state(subscription, "free", "subscription_inactive")

        return cls._state(subscription, "free", "subscription_status_unknown")

    @staticmethod
    def _state(subscription, plan, reason):
        return {
            "organization_id": getattr(subscription, "organization_id", None),
            "subscription_id": getattr(subscription, "id", None),
            "plan": plan,
            "status": getattr(subscription, "status", None),
            "effective_plan": plan,
            "active": plan != "free" and reason == "active",
            "reason": reason,
            "database_mutation": False,
            "external_execution": False,
        }


subscription_state_service = SubscriptionStateService()
