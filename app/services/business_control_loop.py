from datetime import datetime, timezone
from typing import Any

from app.services.outcome_priority import OutcomePriorityService
from app.services.decision_lifecycle import DecisionLifecycleService
from app.services.decision_learning import decision_learning
from app.services.decision_intelligence import decision_intelligence


class BusinessControlLoopService:
    VERSION = "1.1"
    STATES = ("detected", "ranked", "reviewed", "approved", "executed", "outcome_observed")

    @classmethod
    def build(cls, organization_id: int | None, decisions: list[dict[str, Any]] | None = None, period: str = "30d") -> dict[str, Any]:
        if not organization_id:
            return {"success": False, "error": "organization_required", "engine": "kemet_business_control_loop", "version": cls.VERSION}
        ranked = OutcomePriorityService.rank(organization_id, decisions or [], period=period)
        items = ranked.get("items", ranked.get("decisions", [])) if ranked.get("success") else []
        learning = decision_learning.enrich(organization_id, items, period=period)
        learned_items = learning.get("decisions", items) if learning.get("success") else items
        intelligence = decision_intelligence.build(organization_id, learned_items, period=period)
        intelligent_items = intelligence.get("decisions", learned_items) if intelligence.get("success") else learned_items
        projected = DecisionLifecycleService.project(organization_id, intelligent_items, period=period)
        return {
            "success": True, "engine": "kemet_business_control_loop", "version": cls.VERSION,
            "organization_id": organization_id, "period": period,
            "loop": list(cls.STATES),
            "decisions": projected.get("items", []) if projected.get("success") else [],
            "count": len(projected.get("items", [])) if projected.get("success") else 0,
            "learning": {
                "enabled": learning.get("success", False),
                "mode": "observational",
                "signals": learning.get("aggregate", {}) if learning.get("success") else {},
                "ranking_adjustment": "recommendation_only",
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
