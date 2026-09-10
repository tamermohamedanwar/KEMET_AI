from __future__ import annotations

from typing import Any

from app.services.capability_registry import capability_registry


class BusinessOutcomeAttribution:
    """Conservative read-only attribution; no unsupported causal ROI claims."""

    VERSION = "1.0"

    @staticmethod
    def _measurement_contract(capability: dict[str, Any]) -> dict[str, Any]:
        domain = str(capability.get("domain") or "general").lower()
        metric_map = {
            "executive": ["paid_amount", "leads_total", "tickets_open"],
            "sales": ["leads_total", "paid_amount", "subscriptions_active"],
            "finance": ["paid_amount", "payments_failed", "subscriptions_active"],
            "support": ["tickets_open", "tickets_closed"],
        }
        metrics = metric_map.get(domain, ["paid_amount", "leads_total"])
        return {
            "version": "1.0",
            "domain": domain,
            "metrics": metrics,
            "window": "30d",
            "interpretation": "observational_change_only",
        }

    @classmethod
    def build(cls, organization_id: int | None, capability_id: str,
              before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        if not organization_id:
            return {"success": False, "error": "organization_required"}
        capability = capability_registry.get(capability_id)
        if not capability:
            return {"success": False, "error": "capability_not_found"}
        deltas = {}
        for key in set(before) | set(after):
            old, new = before.get(key), after.get(key)
            if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                deltas[key] = new - old
        contract = cls._measurement_contract(capability)
        relevant_deltas = {
            key: deltas[key] for key in contract["metrics"] if key in deltas
        }
        return {
            "success": True, "engine": "kemet_business_outcome_attribution",
            "version": cls.VERSION, "organization_id": organization_id,
            "capability_id": capability_id,
            "measurement": {
                "contract": contract,
                "relevant_deltas": relevant_deltas,
                "coverage": round(len(relevant_deltas) / len(contract["metrics"]), 4) if contract["metrics"] else 0.0,
            },
            "observed": {"before": before, "after": after, "deltas": deltas},
            "attribution": {"level": "observational", "causal_claim": False, "roi_claim": False},
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
        }
