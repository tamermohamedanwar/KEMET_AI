from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.models.automation import AutomationExecution
from app.models.automation_outcome import AutomationOutcome
from app.services.execution_entitlement_service import ExecutionEntitlementService


class BusinessThroughputService:
    """Read-only business throughput metrics for governed operations."""

    VERSION = "1.1"
    PERIOD_DAYS = {"24h": 1, "7d": 7, "30d": 30, "90d": 90}

    @classmethod
    def build(cls, organization_id: int | None, period: str = "30d") -> dict[str, Any]:
        if not organization_id:
            return {"success": False, "error": "organization_required"}

        period = period if period in cls.PERIOD_DAYS else "30d"
        since = datetime.utcnow() - timedelta(days=cls.PERIOD_DAYS[period])
        entitlement = ExecutionEntitlementService.check(int(organization_id))

        outcomes = (
            AutomationOutcome.query
            .filter(
                AutomationOutcome.organization_id == organization_id,
                AutomationOutcome.created_at >= since,
            )
            .all()
        )
        executions = (
            AutomationExecution.query
            .join(AutomationExecution.workflow)
            .filter(AutomationExecution.created_at >= since)
            .filter(AutomationExecution.workflow.has(organization_id=organization_id))
            .all()
        )

        total = len(outcomes)
        successful = sum(1 for item in outcomes if item.status == "completed" and item.executed)
        failed = sum(1 for item in outcomes if item.status in {"failed", "error"})
        executed = sum(1 for item in outcomes if item.executed)
        durations = [item.duration_ms for item in outcomes if item.duration_ms is not None]
        costs = [Decimal(str(item.cost_amount)) for item in outcomes if item.cost_amount is not None]
        outcome_types = {}
        for item in outcomes:
            key = item.business_outcome or "unspecified"
            outcome_types[key] = outcome_types.get(key, 0) + 1

        success_rate = round((successful / executed) * 100, 2) if executed else None
        avg_duration = round(sum(durations) / len(durations), 2) if durations else None
        total_cost = float(sum(costs)) if costs else 0.0
        completed_executions = sum(1 for item in executions if item.status == "completed")
        waiting_approval = sum(1 for item in executions if item.status in {"waiting_approval", "pending"})
        throughput_per_day = round(successful / cls.PERIOD_DAYS[period], 2)
        cost_per_successful = round(total_cost / successful, 6) if successful else None

        return {
            "success": True,
            "engine": "kemet_business_throughput",
            "version": cls.VERSION,
            "organization_id": organization_id,
            "period": period,
            "generated_at": datetime.utcnow().isoformat(),
            "metrics": {
                "throughput_per_day": throughput_per_day,
                "successful_outcomes": successful,
                "executed_outcomes": executed,
                "total_outcomes": total,
                "failed_outcomes": failed,
                "success_rate_percent": success_rate,
                "avg_time_to_outcome_ms": avg_duration,
                "total_recorded_cost": total_cost,
                "cost_per_successful_outcome": cost_per_successful,
                "completed_workflows": completed_executions,
                "waiting_for_approval": waiting_approval,
                "business_outcomes": outcome_types,
            },
            "commercial_capacity": {
                "plan": entitlement.get("plan"),
                "monthly_limit": entitlement.get("limit"),
                "used_this_month": entitlement.get("used"),
                "remaining_this_month": entitlement.get("remaining"),
                "month": entitlement.get("month"),
                "admission_allowed": entitlement.get("allowed", False),
                "reason": entitlement.get("reason"),
            },
            "business": {
                "measure": "outcomes, not implementation volume",
                "time_to_outcome_ms": avg_duration,
                "cost_per_successful_outcome": cost_per_successful,
                "throughput_per_day": throughput_per_day,
            },
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "causal_claim": False,
                "roi_claim": False,
            },
        }


business_throughput_service = BusinessThroughputService()
