from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.automation_execution_ledger import AutomationExecutionLedger
from app.services.entitlement_service import EntitlementService


class ExecutionEntitlementService:
    """Commercial admission for governed execution capacity."""

    VERSION = "1.0"
    MONTHLY_LIMITS = {
        "free": 0,
        "starter": 100,
        "business": 1000,
        "enterprise": 10000,
    }

    @classmethod
    def check(cls, organization_id: int | None, execution_key: str | None = None) -> dict[str, Any]:
        if not organization_id:
            return cls._blocked("organization_required")
        try:
            entitlement = EntitlementService.require_feature(organization_id, "automation")
        except Exception:
            return cls._blocked("entitlement_check_failed")
        if not entitlement.get("allowed"):
            return cls._blocked(
                "automation_feature_not_available",
                plan=entitlement.get("plan"),
            )
        plan = str(entitlement.get("plan") or "free").lower()
        limit = int(cls.MONTHLY_LIMITS.get(plan, 0))
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        query = AutomationExecutionLedger.query.filter(
            AutomationExecutionLedger.organization_id == int(organization_id),
            AutomationExecutionLedger.created_at >= month_start,
        )
        reserved = query.count()
        duplicate = False
        if execution_key:
            duplicate = query.filter(
                AutomationExecutionLedger.execution_key == str(execution_key)
            ).first() is not None
        if not duplicate and reserved >= limit:
            return cls._blocked(
                "execution_entitlement_limit_reached",
                plan=plan, limit=limit, used=reserved, remaining=0,
            )
        return {
            "allowed": True,
            "plan": plan,
            "limit": limit,
            "used": reserved,
            "remaining": max(limit - reserved - (0 if duplicate else 1), 0),
            "execution_key": execution_key,
            "month": month_start.strftime("%Y-%m"),
            "reason": "execution_entitlement_allowed",
            "governance": cls._governance(),
        }

    @classmethod
    def _blocked(cls, reason: str, **extra: Any) -> dict[str, Any]:
        return {
            "allowed": False,
            "reason": reason,
            **extra,
            "governance": cls._governance(),
        }

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "read_only": True,
            "advisory": False,
            "external_execution": False,
            "database_mutation": False,
            "auto_execute": False,
        }


execution_entitlement_service = ExecutionEntitlementService()
