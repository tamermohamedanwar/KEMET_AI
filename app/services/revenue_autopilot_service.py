from app.automation.action_registry import registry
from app.automation.dispatcher import dispatcher
from app.services.revenue_event_service import RevenueEventService


class RevenueAutopilotService:
    """
    Converts revenue events into safe, deterministic automation actions.

    This service does not send external messages by itself.
    It routes qualified revenue events into the existing ActionRegistry.
    """

    EVENT_ACTIONS = {
        RevenueEventService.EVENT_LEAD_HOT: (
            "ai_sales_qualification",
            "Hot lead requires immediate sales qualification.",
        ),
        RevenueEventService.EVENT_LEAD_HIGH_VALUE: (
            "revenue_opportunity",
            "High-value lead detected.",
        ),
        RevenueEventService.EVENT_LEAD_FOLLOWUP_DUE: (
            "sales_follow_up",
            "Lead follow-up is due today.",
        ),
        RevenueEventService.EVENT_LEAD_FOLLOWUP_OVERDUE: (
            "sales_follow_up",
            "Lead follow-up is overdue.",
        ),
        RevenueEventService.EVENT_LEAD_STALE: (
            "customer_retention",
            "Lead has become stale and should be re-engaged.",
        ),
        RevenueEventService.EVENT_LEAD_CONVERTED: (
            "customer_lifecycle",
            "Lead converted and entered the customer lifecycle.",
        ),
    }

    @classmethod
    def build_plan(cls, events):
        plan = []

        for event in events or []:
            event_name = event.get("event")
            data = event.get("data") or {}

            action_info = cls.EVENT_ACTIONS.get(event_name)

            if not action_info:
                continue

            action_type, reason = action_info

            if not registry.exists(action_type):
                plan.append({
                    "event": event_name,
                    "action": action_type,
                    "status": "unavailable",
                    "reason": reason,
                    "data": data,
                })
                continue

            plan.append({
                "event": event_name,
                "action": action_type,
                "status": "ready",
                "reason": reason,
                "data": data,
            })

        return cls._deduplicate(plan)

    @staticmethod
    def _deduplicate(plan):
        seen = set()
        result = []

        for item in plan:
            key = (
                item.get("data", {}).get("lead_id"),
                item.get("action"),
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(item)

        return result

    @classmethod
    def execute_plan(
        cls,
        plan,
        user_id=None,
        organization_id=None,
        dry_run=False,
    ):
        from app.workforce.selector import workforce_selector

        results = []

        for item in plan or []:
            action = item.get("action")
            parameters = dict(item.get("data") or {})

            parameters["revenue_event"] = item.get("event")
            parameters["revenue_reason"] = item.get("reason")

            if item.get("status") != "ready":
                results.append({
                    **item,
                    "execution": "skipped",
                })
                continue

            if organization_id is None:
                results.append({
                    **item,
                    "execution": "blocked",
                    "governance": {
                        "status": "blocked",
                        "error": "organization_required",
                    },
                    "result": {
                        "success": False,
                        "status": "blocked",
                        "error": "organization_required",
                    },
                })
                continue

            selection = workforce_selector.select(
                action=action,
            )

            if not selection.get("success"):
                results.append({
                    **item,
                    "execution": "blocked",
                    "governance": {
                        "status": "blocked",
                        "error": selection.get("error"),
                    },
                    "result": selection,
                })
                continue

            workforce_id = selection.get("workforce_id")
            requires_approval = bool(
                selection.get("requires_approval")
            )

            governance = {
                "status": "selected",
                "workforce_id": workforce_id,
                "requires_approval": requires_approval,
            }

            if dry_run:
                results.append({
                    **item,
                    "execution": "planned",
                    "governance": governance,
                })
                continue

            result = dispatcher.dispatch(
                action=action,
                organization_id=organization_id,
                data={
                    **parameters,
                    "user_id": user_id,
                    "workforce_id": workforce_id,
                    "revenue_autopilot": True,
                },
            )

            if result.get("success"):
                execution_status = "completed"
            elif result.get("status") == "waiting_approval":
                execution_status = "waiting_approval"
            else:
                execution_status = "failed"

            results.append({
                **item,
                "execution": execution_status,
                "governance": governance,
                "result": result,
            })

        return results
    @classmethod
    def process_lead(
        cls,
        lead,
        user_id=None,
        organization_id=None,
        execute=False,
    ):
        events = RevenueEventService.build_events(lead)

        plan = cls.build_plan(events)

        if not execute:
            return {
                "lead_id": lead.id,
                "events": events,
                "plan": plan,
                "status": "planned",
            }

        results = cls.execute_plan(
            plan,
            user_id=user_id,
            organization_id=organization_id,
        )

        return {
            "lead_id": lead.id,
            "events": events,
            "plan": plan,
            "results": results,
            "status": "executed",
        }


    @classmethod
    def process_leads(
        cls,
        leads,
        user_id=None,
        organization_id=None,
        execute=False,
        limit=100,
    ):
        processed = 0
        planned = 0
        executed = 0
        failed = 0
        output = []

        for lead in list(leads or [])[:limit]:
            result = cls.process_lead(
                lead,
                user_id=user_id,
                organization_id=organization_id,
                execute=execute,
            )

            processed += 1

            if result["status"] == "planned":
                planned += len(result.get("plan") or [])

            for item in result.get("results") or []:
                if item.get("execution") == "completed":
                    executed += 1
                elif item.get("execution") == "failed":
                    failed += 1

            output.append(result)

        return {
            "processed_leads": processed,
            "planned_actions": planned,
            "executed_actions": executed,
            "failed_actions": failed,
            "execute": execute,
            "results": output,
        }
