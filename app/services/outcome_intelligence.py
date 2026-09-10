from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.kpi_service import KPIService
from app.services.business_outcome_attribution import BusinessOutcomeAttribution
from app.services.capability_registry import capability_registry


class OutcomeIntelligenceService:
    """Read-only observed-impact intelligence; never claims causality."""

    VERSION = "1.0"

    SIGNALS = {
        "kemet.lead_scoring": ["leads_total"],
        "kemet.ai_sales_qualification": ["leads_total"],
        "kemet.sales_follow_up": ["leads_total", "paid_amount"],
        "kemet.revenue_opportunity": ["paid_amount"],
        "kemet.customer_retention": ["subscriptions_active"],
        "kemet.churn_detection": ["subscriptions_active"],
        "kemet.payment_issue": ["paid_amount", "payments_failed"],
        "kemet.smart_ticket_ai": ["tickets_open", "tickets_closed"],
        "kemet.business_insights": ["paid_amount", "leads_total", "tickets_open"],
    }

    @classmethod
    def _snapshot(cls, organization_id: int, period: str) -> dict[str, Any]:
        kpis = KPIService.get_kpis(organization_id=organization_id, period=period)
        return {
            "paid_amount": kpis.get("revenue", {}).get("paid_amount", 0.0),
            "payments_failed": kpis.get("revenue", {}).get("payments_failed", 0),
            "subscriptions_active": kpis.get("revenue", {}).get("subscriptions_active", 0),
            "leads_total": kpis.get("sales", {}).get("leads_total", 0),
            "tickets_open": kpis.get("support", {}).get("tickets_open", 0),
            "tickets_closed": kpis.get("support", {}).get("tickets_closed", 0),
        }

    @classmethod
    def _confidence(cls, before, after, signals):
        available = [k for k in signals if isinstance(before.get(k), (int, float)) and isinstance(after.get(k), (int, float))]
        if not available:
            return 0.0, "insufficient_data"
        coverage = len(available) / max(len(signals), 1)
        changed = any(float(after[k]) != float(before[k]) for k in available)
        if not changed:
            return round(0.45 * coverage, 2), "low_signal"
        return round(min(0.55 + 0.35 * coverage, 0.90), 2), "observed_change"

    @classmethod
    def build(cls, organization_id: int | None, capability_id: str, period: str = "30d") -> dict[str, Any]:
        if not organization_id:
            return {"success": False, "error": "organization_required", "engine": "kemet_outcome_intelligence", "version": cls.VERSION}
        if not capability_registry.get(capability_id):
            return {"success": False, "error": "capability_not_found", "engine": "kemet_outcome_intelligence", "version": cls.VERSION}
        period = period if period in KPIService.PERIODS else "30d"
        after = cls._snapshot(organization_id, period)
        before = cls._snapshot(organization_id, "90d")
        signals = cls.SIGNALS.get(capability_id, [])
        confidence, confidence_reason = cls._confidence(before, after, signals)
        observed = BusinessOutcomeAttribution.build(organization_id, capability_id, before, after)
        observed_data = observed.get("observed", {}) if observed.get("success") else {}
        baseline = observed_data.get("before", before)
        current = observed_data.get("after", after)
        deltas = observed_data.get("deltas", {})
        impact = []
        for key in signals:
            old, new = baseline.get(key, 0), current.get(key, 0)
            delta = deltas.get(key, 0)
            change_pct = round((delta / abs(old)) * 100, 2) if isinstance(old, (int, float)) and old != 0 and isinstance(delta, (int, float)) else None
            impact.append({"metric": key, "before": old, "after": new, "delta": delta, "change_percent": change_pct,
                           "direction": "positive" if delta > 0 else "negative" if delta < 0 else "flat"})
        return {
            "success": True, "engine": "kemet_outcome_intelligence", "version": cls.VERSION,
            "organization_id": organization_id, "capability_id": capability_id, "period": period,
            "baseline_window": "90d", "observation_window": period, "observed_impact": impact,
            "confidence": {"score": confidence, "level": "high" if confidence >= .80 else "medium" if confidence >= .55 else "low", "reason": confidence_reason, "data_sufficiency": len([x for x in signals if x in deltas]) / max(len(signals), 1)},
            "attribution": {"level": "observational", "causal_claim": False, "roi_claim": False},
            "governance": {"read_only": True, "advisory": True, "external_execution": False, "database_mutation": False},
            "generated_at": datetime.utcnow().isoformat(),
        }

    @classmethod
    def summary(cls, organization_id: int | None, capabilities: list[str] | None = None, period: str = "30d") -> dict[str, Any]:
        if not organization_id:
            return {"success": False, "error": "organization_required", "engine": "kemet_outcome_intelligence", "version": cls.VERSION}
        items = []
        for capability_id in capabilities or list(cls.SIGNALS):
            item = cls.build(organization_id, capability_id, period)
            if item.get("success"):
                items.append(item)
        return {"success": True, "engine": "kemet_outcome_intelligence", "version": cls.VERSION, "organization_id": organization_id, "period": period, "items": items, "count": len(items), "governance": {"read_only": True, "causal_claim": False, "roi_claim": False, "external_execution": False, "database_mutation": False}}


outcome_intelligence = OutcomeIntelligenceService()

