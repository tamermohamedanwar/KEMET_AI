from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from app.services.kpi_service import KPIService
from app.services.bos_intelligence import BOSIntelligenceService
from app.services.business_outcome_attribution import BusinessOutcomeAttribution
from app.services.capability_registry import capability_registry


class BusinessOutcomeService:
    """Read-only executive outcome layer for Kemet BOS."""

    VERSION = "1.0"

    @classmethod
    def capture_snapshot(cls, organization_id: int | None, period: str = "30d") -> Dict[str, Any]:
        """Capture a read-only KPI baseline for a governed execution."""
        if not organization_id:
            return {"success": False, "error": "organization_required"}
        period = period if period in KPIService.PERIODS else "30d"
        kpis = KPIService.get_kpis(organization_id=organization_id, period=period)
        return {
            "success": True,
            "period": period,
            "captured_at": datetime.utcnow().isoformat(),
            "metrics": {
                "paid_amount": kpis.get("revenue", {}).get("paid_amount", 0.0),
                "payments_failed": kpis.get("revenue", {}).get("payments_failed", 0),
                "subscriptions_active": kpis.get("revenue", {}).get("subscriptions_active", 0),
                "leads_total": kpis.get("sales", {}).get("leads_total", 0),
                "tickets_open": kpis.get("support", {}).get("tickets_open", 0),
                "tickets_closed": kpis.get("support", {}).get("tickets_closed", 0),
            },
        }

    @classmethod
    def build_execution_outcome(cls, organization_id: int | None, capability_id: str, baseline: Dict[str, Any], period: str = "30d") -> Dict[str, Any]:
        """Produce an observational execution outcome receipt; never claims causality."""
        if not organization_id:
            return {"success": False, "error": "organization_required"}
        if not capability_registry.get(capability_id):
            return {"success": False, "error": "capability_not_found"}
        current = cls.capture_snapshot(organization_id, period)
        if not current.get("success"):
            return current
        before = (baseline or {}).get("metrics", {})
        after = current.get("metrics", {})
        attribution = BusinessOutcomeAttribution.build(organization_id, capability_id, before, after)
        return {
            "success": True,
            "engine": "kemet_execution_outcome",
            "version": "1.0",
            "organization_id": organization_id,
            "capability_id": capability_id,
            "baseline": baseline,
            "measurement": attribution.get("measurement", {}),
            "observed": attribution.get("observed", {}),
            "attribution": {"level": "observational", "causal_claim": False, "roi_claim": False},
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
            "captured_at": current.get("captured_at"),
        }

    @classmethod
    def build(cls, organization_id: int | None, period: str = "30d") -> Dict[str, Any]:
        if not organization_id:
            return {
                "success": False,
                "error": "organization_required",
                "engine": "kemet_outcome",
                "version": cls.VERSION,
            }

        period = period if period in KPIService.PERIODS else "30d"
        kpis = KPIService.get_kpis(organization_id=organization_id, period=period)
        snapshot = BOSIntelligenceService.get_executive_snapshot(
            organization_id=organization_id,
            limit=5,
        )

        automation = kpis.get("automation", {})
        revenue = kpis.get("revenue", {})
        sales = kpis.get("sales", {})
        support = kpis.get("support", {})

        execution_total = int(automation.get("total_executions", 0) or 0)
        execution_success = int(automation.get("successful_executions", 0) or 0)
        execution_failed = int(automation.get("failed_executions", 0) or 0)

        if execution_total:
            execution_health = automation.get("success_rate", 0.0)
        else:
            execution_health = None

        health_score = float(snapshot.get("health_score", 0) or 0)
        high_priority = int((snapshot.get("counts") or {}).get("high", 0) or 0)

        if health_score >= 85 and execution_failed == 0:
            outcome_status = "strong"
        elif health_score >= 70 and execution_failed <= execution_success:
            outcome_status = "healthy"
        elif high_priority:
            outcome_status = "needs_attention"
        else:
            outcome_status = "monitor"

        from app.automation.playbook_engine import playbook_engine

        opportunities = []
        from app.services.outcome_intelligence import outcome_intelligence
        from app.services.capability_registry import capability_registry
        for decision in snapshot.get("decisions", [])[:5]:
            action = decision.get("action") or decision.get("executable_action")
            definition = playbook_engine.get_definition(action) if action else None
            capability_id = f"kemet.{action}" if action else None
            impact = outcome_intelligence.build(organization_id, capability_id, period) if capability_id and capability_registry.get(capability_id) else {}
            opportunities.append({
                "decision_id": decision.get("decision_id") or decision.get("id"),
                "title": decision.get("title", "Business decision"),
                "priority": decision.get("priority", "low"),
                "action": action,
                "capability_id": capability_id,
                "playbook": definition,
                "expected_outcome": decision.get("expected_outcome", ""),
                "observed_impact": impact.get("observed_impact", []),
                "impact_confidence": impact.get("confidence", {"score": 0, "level": "low", "reason": "not_available"}),
            })

        from app.services.outcome_priority import outcome_priority
        priority_result = outcome_priority.rank(organization_id, opportunities, period)
        ranked_opportunities = (
            priority_result.get("items", [])
            if priority_result.get("success")
            else opportunities
        )

        return {
            "success": True,
            "engine": "kemet_outcome",
            "version": cls.VERSION,
            "organization_id": organization_id,
            "period": period,
            "generated_at": datetime.utcnow().isoformat(),
            "status": outcome_status,
            "executive_summary": snapshot.get("summary", ""),
            "health_score": health_score,
            "business": {
                "leads": sales.get("leads_total", 0),
                "open_tickets": support.get("tickets_open", 0),
                "paid_amount": revenue.get("paid_amount", 0.0),
                "active_subscriptions": revenue.get("subscriptions_active", 0),
            },
            "automation": {
                "executions": execution_total,
                "successful": execution_success,
                "failed": execution_failed,
                "success_rate": execution_health,
            },
            "roi": {
                "revenue": revenue.get("paid_amount", 0.0),
                "automation_success_rate": execution_health,
            },
            "decisions": ranked_opportunities,
            "next_best_actions": ranked_opportunities[:3],
            "governance": {
                "mode": "advisory",
                "requires_approval": True,
                "external_execution": False,
                "database_mutation": False,
            },
        }


business_outcome_service = BusinessOutcomeService()
