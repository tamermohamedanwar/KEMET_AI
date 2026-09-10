from __future__ import annotations

from app.models.automation import AutomationWorkflow, AutomationAction
from app.automation.engine import engine


class ExecutionDispatcher:
    """
    Dispatches a validated Orchestrator action to an existing
    organization-owned automation workflow.

    Direct BOS commands prefer workflows that contain exactly one
    active action. This prevents a direct action from accidentally
    executing a larger business workflow.
    """

    def dispatch(
        self,
        action: str,
        organization_id: int,
        data: dict | None = None,
    ) -> dict:
        if not action:
            return {
                "success": False,
                "status": "blocked",
                "error": "action_required",
            }

        if not organization_id:
            return {
                "success": False,
                "status": "blocked",
                "error": "organization_required",
            }

        data = dict(data or {})
        data["organization_id"] = organization_id

        candidates = (
            AutomationWorkflow.query
            .filter_by(
                organization_id=organization_id,
                is_active=True,
            )
            .order_by(AutomationWorkflow.id.asc())
            .all()
        )

        direct_matches = []

        for workflow in candidates:
            actions = (
                AutomationAction.query
                .filter_by(
                    workflow_id=workflow.id,
                    is_active=True,
                )
                .order_by(AutomationAction.position.asc())
                .all()
            )

            if len(actions) != 1:
                continue

            if actions[0].action_type != action:
                continue

            direct_matches.append(workflow)

        if not direct_matches:
            return {
                "success": False,
                "status": "blocked",
                "error": "direct_workflow_not_found",
                "action": action,
                "organization_id": organization_id,
            }

        workflow = direct_matches[0]

        engine_result = engine.execute(
            workflow_id=workflow.id,
            data=data,
            organization_id=organization_id,
        )

        results = (
            engine_result
            if isinstance(engine_result, list)
            else [engine_result]
        )

        statuses = {
            item.get("status")
            for item in results
            if isinstance(item, dict)
        }

        if "waiting_approval" in statuses or "pending" in statuses:
            status = "waiting_approval"
            success = False
        elif "failed" in statuses:
            status = "failed"
            success = False
        elif "blocked" in statuses:
            status = "blocked"
            success = False
        elif "rejected" in statuses:
            status = "rejected"
            success = False
        elif "deduplicated" in statuses:
            status = "deduplicated"
            success = True
        elif "completed" in statuses:
            status = "completed"
            success = True
        else:
            status = "dispatched"
            success = bool(engine_result)

        return {
            "success": success,
            "status": status,
            "action": action,
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "trigger_type": workflow.trigger_type,
            "result": engine_result,
        }


dispatcher = ExecutionDispatcher()
