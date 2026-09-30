from datetime import datetime, timezone
from typing import Any

from app.services.outcome_priority import OutcomePriorityService
from app.services.decision_lifecycle import DecisionLifecycleService
from app.services.decision_learning import decision_learning
from app.services.decision_intelligence import decision_intelligence
from app.services.cross_channel_outcome_learning import cross_channel_outcome_learning
from app.services.revenue_content_decision_signal_service import revenue_content_decision_signal_service


class BusinessControlLoopService:
    VERSION = "1.1"
    STATES = ("detected", "ranked", "reviewed", "approved", "executed", "outcome_observed")

    @classmethod
    def build(cls, organization_id: int | None, decisions: list[dict[str, Any]] | None = None, period: str = "30d", execution_keys: list[str] | None = None, revenue_intelligence: dict[str, Any] | None = None) -> dict[str, Any]:
        if not organization_id:
            return {"success": False, "error": "organization_required", "engine": "kemet_business_control_loop", "version": cls.VERSION}
        ranked = OutcomePriorityService.rank(organization_id, decisions or [], period=period)
        items = ranked.get("items", ranked.get("decisions", [])) if ranked.get("success") else []
        learning = decision_learning.enrich(organization_id, items, period=period)
        learned_items = learning.get("decisions", items) if learning.get("success") else items
        intelligence = decision_intelligence.build(organization_id, learned_items, period=period)
        intelligent_items = intelligence.get("decisions", learned_items) if intelligence.get("success") else learned_items
        projected = DecisionLifecycleService.project(organization_id, intelligent_items, period=period)
        cross_channel = cross_channel_outcome_learning.build(organization_id, execution_keys=execution_keys or [], period=period)
        revenue_signals = revenue_content_decision_signal_service.build(
            organization_id=organization_id,
            intelligence=revenue_intelligence or {"records": []},
        )
        return {
            "success": True, "engine": "kemet_business_control_loop", "version": cls.VERSION,
            "organization_id": organization_id, "period": period,
            "loop": list(cls.STATES),
            "marketing_intelligence": {
                "enabled": True,
                "pipeline": [
                    "research",
                    "audience_intelligence",
                    "content_strategy",
                    "experiment",
                    "campaign_governance",
                    "human_approval",
                    "outcome_measurement",
                    "learning",
                    "next_action",
                ],
                "external_execution": False,
                "automatic_action": False,
                "requires_human_approval": True,
            },
            "decisions": projected.get("items", []) if projected.get("success") else [],
            "count": len(projected.get("items", [])) if projected.get("success") else 0,
            "learning": {
                "enabled": learning.get("success", False),
                "mode": "observational",
                "signals": learning.get("aggregate", {}) if learning.get("success") else {},
                "ranking_adjustment": "recommendation_only",
            },
            "cross_channel_outcome_learning": {
                "enabled": cross_channel.get("success", False),
                "status": cross_channel.get("status"),
                "learning_digest": cross_channel.get("learning_digest"),
                "next_action": (cross_channel.get("learning") or {}).get("next_action"),
                "comparison": (cross_channel.get("learning") or {}).get("cross_channel_comparison"),
                "governance": cross_channel.get("governance", {}),
            },
            "revenue_decision_signals": {
                "enabled": revenue_signals.get("success", False),
                "verified_revenue": (revenue_signals.get("signals") or {}).get("verified_revenue", 0.0),
                "verified_content_count": (revenue_signals.get("signals") or {}).get("verified_content_count", 0),
                "authoritatively_measured_content_count": (revenue_signals.get("signals") or {}).get("authoritatively_measured_content_count", 0),
                "decision_basis": (revenue_signals.get("decision_support") or {}).get("basis"),
                "automatic_action": False,
                "external_action": False,
                "causal_claim": False,
                "roi_claim": False,
            },
            "decision_intelligence": {
                "enabled": intelligence.get("success", False),
                "engine_version": decision_intelligence.VERSION,
                "ranking": "advisory_only",
            },
            "governance": {"advisory": True, "requires_human_approval": True, "external_execution": False, "database_mutation": False},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "control_policy": {
                "auto_execute": False,
                "human_approval_required": True,
                "fail_closed": True,
                "learning_mode": "observational",
            },
        }


business_control_loop = BusinessControlLoopService()
