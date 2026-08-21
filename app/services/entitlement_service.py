"""
Kemet AI — SaaS Entitlement Service

Pure application-layer entitlement logic.
No database mutation.
No external execution.
"""

from app.services.ai_usage_service import (
    PLAN_LIMITS,
    get_plan,
    check_limit,
)


class EntitlementService:
    """
    Central SaaS entitlement policy.

    This layer intentionally does not mutate the database.
    """

    FEATURES = {
        "free": {
            "ai": True,
            "crm": True,
            "support": True,
            "automation": False,
            "bos": False,
            "executive_control_center": False,
            "governance": False,
            "advanced_analytics": False,
            "api_access": False,
        },
        "starter": {
            "ai": True,
            "crm": True,
            "support": True,
            "automation": True,
            "bos": True,
            "executive_control_center": True,
            "governance": True,
            "advanced_analytics": False,
            "api_access": False,
        },
        "business": {
            "ai": True,
            "crm": True,
            "support": True,
            "automation": True,
            "bos": True,
            "executive_control_center": True,
            "governance": True,
            "advanced_analytics": True,
            "api_access": True,
        },
        "enterprise": {
            "ai": True,
            "crm": True,
            "support": True,
            "automation": True,
            "bos": True,
            "executive_control_center": True,
            "governance": True,
            "advanced_analytics": True,
            "api_access": True,
        },
    }

    FEATURE_ALIASES = {
        "executive": "executive_control_center",
        "control_center": "executive_control_center",
        "analytics": "advanced_analytics",
        "api": "api_access",
    }

    @classmethod
    def normalize_plan(cls, plan):
        value = str(plan or "free").strip().lower()

        if value not in cls.FEATURES:
            return "free"

        return value

    @classmethod
    def resolve_feature(cls, feature):
        value = str(feature or "").strip().lower()
        return cls.FEATURE_ALIASES.get(value, value)

    @classmethod
    def plan(cls, organization_id):
        """
        Resolve the effective SaaS plan from the active subscription.

        The subscription is the authoritative commercial entitlement
        source. Usage service remains the fallback for compatibility.
        """
        try:
            from app.models import Subscription

            subscription = (
                Subscription.query
                .filter_by(organization_id=organization_id)
                .order_by(Subscription.id.desc())
                .first()
            )

            if subscription:
                status = str(
                    getattr(subscription, "status", "") or ""
                ).strip().lower()

                subscription_plan = getattr(
                    subscription,
                    "plan",
                    None,
                )

                if subscription_plan and (
                    not status
                    or status in {
                        "active",
                        "trial",
                        "trialing",
                    }
                ):
                    return cls.normalize_plan(
                        subscription_plan
                    )

        except Exception:
            pass

        usage_plan = get_plan(organization_id)

        if isinstance(usage_plan, (tuple, list)):
            usage_plan = (
                usage_plan[0]
                if usage_plan
                else "free"
            )

        return cls.normalize_plan(usage_plan)

    @classmethod
    def feature_enabled(cls, organization_id, feature):
        plan = cls.plan(organization_id)
        feature = cls.resolve_feature(feature)

        return bool(
            cls.FEATURES
            .get(plan, {})
            .get(feature, False)
        )

    @classmethod
    def require_feature(cls, organization_id, feature):
        plan = cls.plan(organization_id)
        feature = cls.resolve_feature(feature)
        enabled = cls.feature_enabled(
            organization_id,
            feature,
        )

        return {
            "allowed": enabled,
            "plan": plan,
            "feature": feature,
            "reason": (
                "feature_enabled"
                if enabled
                else "feature_not_available_on_plan"
            ),
        }

    @classmethod
    def usage(cls, organization_id):
        result = check_limit(organization_id)

        return {
            "allowed": bool(result.get("allowed")),
            "plan": cls.normalize_plan(
                result.get("plan")
            ),
            "limit": result.get("limit", 0),
            "used": result.get("used", 0),
            "remaining": result.get("remaining", 0),
        }

    @classmethod
    def overview(cls, organization_id):
        plan = cls.plan(organization_id)
        usage = cls.usage(organization_id)

        features = dict(
            cls.FEATURES.get(
                plan,
                cls.FEATURES["free"],
            )
        )

        return {
            "success": True,
            "organization_id": organization_id,
            "plan": plan,
            "usage": usage,
            "features": features,
            "database_mutation": False,
            "external_execution": False,
        }
