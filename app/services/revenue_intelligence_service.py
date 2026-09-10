"""Read-only SaaS revenue intelligence for Kemet.

Metrics are derived from authoritative subscription state and plan prices.
No payment, subscription, or external state is mutated here.
"""

from decimal import Decimal

from app.config.plans import PLAN_DETAILS
from app.models.subscription import Subscription


ACTIVE_STATUSES = {"active", "trial", "trialing"}


class RevenueIntelligenceService:
    VERSION = "1.0"

    @classmethod
    def overview(cls, organization_id=None, previous_active=None):
        query = Subscription.query
        if organization_id is not None:
            query = query.filter(Subscription.organization_id == organization_id)

        subscriptions = query.all()
        active = [s for s in subscriptions if cls._is_active(s)]

        mrr = sum(
            (Decimal(str(PLAN_DETAILS.get(cls._plan(s), {}).get("price_usd") or 0))
             for s in active),
            Decimal("0"),
        )
        active_count = len(active)
        arr = mrr * 12
        arpu = mrr / active_count if active_count else Decimal("0")

        plan_mix = {}
        for subscription in active:
            plan = cls._plan(subscription)
            plan_mix[plan] = plan_mix.get(plan, 0) + 1

        result = {
            "version": cls.VERSION,
            "organization_id": organization_id,
            "active_subscriptions": active_count,
            "mrr": cls._money(mrr),
            "arr": cls._money(arr),
            "arpu": cls._money(arpu),
            "plan_mix": plan_mix,
            "total_subscriptions": len(subscriptions),
            "inactive_subscriptions": len(subscriptions) - active_count,
            "metrics_quality": "subscription_pricing_derived",
            "churn_rate": None,
            "churn_basis": "not_calculated_without_period_baseline",
            "expansion_mrr": None,
            "contraction_mrr": None,
            "ltv": None,
            "cac": None,
            "causal_attribution": False,
            "observed_only": True,
            "database_mutation": False,
            "external_execution": False,
            "auto_execute": False,
        }

        if previous_active is not None:
            baseline = max(int(previous_active), 0)
            inactive_from_baseline = max(baseline - active_count, 0)
            result["churn_rate"] = round(
                (inactive_from_baseline / baseline) * 100, 2
            ) if baseline else 0.0
            result["churn_basis"] = "previous_period_active_baseline"

        return result

    @staticmethod
    def _is_active(subscription):
        return str(getattr(subscription, "status", "") or "").strip().lower() in ACTIVE_STATUSES

    @staticmethod
    def _plan(subscription):
        plan = str(getattr(subscription, "plan", "free") or "free").strip().lower()
        return plan if plan in PLAN_DETAILS else "free"

    @staticmethod
    def _money(value):
        return float(value.quantize(Decimal("0.01")))


revenue_intelligence_service = RevenueIntelligenceService()
