from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.capability_registry import capability_registry


class CapabilityAnalytics:
    """Organization-scoped, read-only execution analytics for capabilities."""

    VERSION = "1.0"

    @classmethod
    def summary(cls, organization_id: int | None) -> dict[str, Any]:
        if not organization_id:
            return {"success": False, "error": "organization_required", "version": cls.VERSION}

        from app.models.automation import AutomationExecution, AutomationWorkflow
        rows = (
            AutomationExecution.query
            .join(AutomationWorkflow, AutomationExecution.workflow_id == AutomationWorkflow.id)
            .filter(AutomationWorkflow.organization_id == organization_id)
            .all()
        )
        total = len(rows)
        successful = sum(1 for row in rows if row.status == "completed")
        failed = sum(1 for row in rows if row.status == "failed")
        waiting = sum(1 for row in rows if row.status == "waiting_approval")
        actions = Counter()
        for row in rows:
            workflow = row.workflow
            action_types = [item.action_type for item in (workflow.actions or [])]
            if action_types:
                actions.update(action_types)
            else:
                actions.update(["unknown"])

        capabilities = []
        for action, count in actions.most_common():
            definition = capability_registry.get(f"kemet.{action}")
            if definition:
                capabilities.append({
                    "capability_id": definition["capability_id"],
                    "action": action,
                    "executions": count,
                    "lifecycle": definition["lifecycle"],
                })

        return {
            "success": True,
            "engine": "kemet_capability_analytics",
            "version": cls.VERSION,
            "organization_id": organization_id,
            "totals": {"executions": total, "successful": successful, "failed": failed, "waiting_approval": waiting},
            "success_rate": (successful / total * 100) if total else None,
            "capabilities": capabilities,
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
        }


capability_analytics = CapabilityAnalytics()


