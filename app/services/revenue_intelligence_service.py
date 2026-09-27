from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from app.config.plans import PLAN_DETAILS
from app.models.subscription import Subscription
from app.services.revenue_identity_reconciliation_service import revenue_identity_reconciliation_service


ACTIVE_STATUSES = {"active", "trial", "trialing"}


class RevenueIntelligenceService:
    """Read-only intelligence derived only from verified commercial evidence."""

    VERSION = "1.1"

    @classmethod
    def overview(cls, organization_id=None, previous_active=None):
        query = Subscription.query
        if organization_id is not None:
            query = query.filter(Subscription.organization_id == organization_id)
        subscriptions = query.all()
        active = [s for s in subscriptions if cls._is_active(s)]
        mrr = sum((Decimal(str(PLAN_DETAILS.get(cls._plan(s), {}).get("price_usd") or 0)) for s in active), Decimal("0"))
        active_count = len(active)
        plan_mix = {}
        for subscription in active:
            plan = cls._plan(subscription)
            plan_mix[plan] = plan_mix.get(plan, 0) + 1
        result = {
            "version": cls.VERSION,
            "organization_id": organization_id,
            "active_subscriptions": active_count,
            "mrr": cls._money(mrr),
            "arr": cls._money(mrr * 12),
            "arpu": cls._money(mrr / active_count if active_count else Decimal("0")),
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
            result["churn_rate"] = round((max(baseline - active_count, 0) / baseline) * 100, 2) if baseline else 0.0
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

    @classmethod
    def analyze(
        cls,
        *,
        organization_id: int,
        content_results: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        records = []
        total_revenue = 0.0
        total_qualified_views = 0.0
        verified_content = 0
        measured_content = 0
        for item in content_results or []:
            if not isinstance(item, Mapping):
                continue
            if int(item.get("organization_id") or organization_id) != int(organization_id):
                continue
            commercial = item.get("commercial") or {}
            revenue = commercial.get("revenue") or {}
            reconciliation = item.get("reconciliation") or {}
            reconciled = reconciliation.get("status") == "reconciled"
            publication = item.get("publication") or {}
            publication_id = str(publication.get("publication_id") or "")
            execution_key = str(item.get("execution_key") or "")
            payment_evidence = item.get("payment_evidence") or item.get("evidence") or []
            reconciled_amount = None
            if payment_evidence:
                try:
                    identity = revenue_identity_reconciliation_service.reconcile(
                        organization_id=int(organization_id),
                        content_id=str(item.get("content_id") or ""),
                        publication_id=publication_id,
                        execution_key=execution_key,
                        evidence=list(payment_evidence),
                    )
                    reconciled = identity.get("status") == "reconciled"
                    transactions = (identity.get("identity") or {}).get("transactions") or []
                    if reconciled:
                        reconciled_amount = sum(cls._nonnegative(tx.get("amount")) for tx in transactions)
                except (TypeError, ValueError):
                    reconciled = False
            provider = item.get("provider_measurement") or {}
            measured = provider.get("verified") is True
            evidence_backed = revenue.get("evidence_backed") is True and reconciled
            economics = commercial.get("economics") or {}
            qualified = cls._nonnegative(economics.get("qualified_views")) if reconciled else 0.0
            amount = (reconciled_amount if reconciled_amount is not None else cls._nonnegative(revenue.get("amount"))) if evidence_backed else 0.0
            if measured:
                measured_content += 1
            if evidence_backed:
                verified_content += 1
                total_revenue += amount
                total_qualified_views += qualified
            rpm = (amount / qualified) * 1000 if evidence_backed and qualified else None
            records.append({
                "content_id": str(item.get("content_id") or ""),
                "channel": str((item.get("publication") or {}).get("channel") or ""),
                "verified_measurement": measured,
                "verified_revenue": evidence_backed,
                "reconciliation_status": "reconciled" if reconciled else "not_reconciled",
                "qualified_views": qualified,
                "verified_revenue_amount": amount if evidence_backed else None,
                "revenue_per_1000_qualified_views": round(rpm, 4) if rpm is not None else None,
                "publication_id": publication_id,
                "execution_key": str(item.get("execution_key") or ""),
                "metric_evidence_digest": str(provider.get("metric_evidence_digest") or ""),
            })
        aggregate_rpm = (total_revenue / total_qualified_views) * 1000 if total_qualified_views else None
        return {
            "success": True,
            "engine": "kemet_revenue_intelligence",
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "signals": {
                "verified_revenue": round(total_revenue, 4),
                "verified_content_count": verified_content,
                "authoritatively_measured_content_count": measured_content,
                "qualified_views_with_verified_revenue": total_qualified_views,
                "revenue_per_1000_qualified_views": round(aggregate_rpm, 4) if aggregate_rpm is not None else None,
                "forecast_is_not_recorded_revenue": True,
            },
            "records": records,
            "decision_support": {
                "basis": "verified_evidence_and_authoritative_measurement",
                "next_decision": "review_content_and_distribution_signals",
                "no_automatic_action": True,
                "causal_claim": False,
                "roi_claim": False,
            },
            "governance": {
                "read_only": True,
                "tenant_scoped": True,
                "database_mutation": False,
                "external_execution": False,
                "execution_authority": False,
                "human_approval_required_for_actions": True,
            },
        }

    @staticmethod
    def _nonnegative(value: Any) -> float:
        try:
            return max(0.0, float(value or 0))
        except (TypeError, ValueError):
            return 0.0


revenue_intelligence_service = RevenueIntelligenceService()
