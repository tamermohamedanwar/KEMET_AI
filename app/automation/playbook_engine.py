from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.automation.workflow_planner import build_steps, summarize_steps


class PlaybookEngine:
    """Build deterministic, reusable, governed business playbooks."""

    VERSION = "2.0"

    PLAYBOOK_CATALOG = {
        "lead_scoring": {"name": "Revenue Pipeline Accelerator", "domain": "sales", "outcome": "Prioritize and qualify the strongest revenue opportunities."},
        "customer_retention": {"name": "Customer Retention Guard", "domain": "customer", "outcome": "Detect churn risk and prepare governed retention follow-up."},
        "sales_follow_up": {"name": "Sales Follow-up Control", "domain": "sales", "outcome": "Prepare prioritized customer follow-up through governed execution."},
        "business_insights": {"name": "Executive Business Review", "domain": "executive", "outcome": "Produce a read-only operating snapshot for management."},
        "churn_detection": {"name": "Churn Risk Monitor", "domain": "customer", "outcome": "Identify customers requiring retention review."},
        "revenue_opportunity": {"name": "Revenue Opportunity Review", "domain": "revenue", "outcome": "Identify and prioritize revenue opportunities."},
        "ai_sales_qualification": {"name": "Lead Qualification Review", "domain": "sales", "outcome": "Prioritize sales-ready opportunities."},
        "order_tracking": {"name": "Order Visibility", "domain": "operations", "outcome": "Return current order tracking state."},
        "payment_issue": {"name": "Payment Operations Review", "domain": "finance", "outcome": "Review payment issues before any financial side effect."},
        "account_help": {"name": "Account Operations Review", "domain": "operations", "outcome": "Review account-related issues safely."},
        "smart_ticket_ai": {"name": "Support Triage", "domain": "support", "outcome": "Review support workload and prioritize cases."},
        "refund_request": {"name": "Refund Control", "domain": "finance", "outcome": "Prepare a refund request for explicit human approval."},
    }

    def catalog(self) -> list[dict[str, Any]]:
        return [{"action": action, **meta} for action, meta in self.PLAYBOOK_CATALOG.items()]

    def get_definition(self, action: str) -> dict[str, Any] | None:
        meta = self.PLAYBOOK_CATALOG.get(action)
        if not meta:
            return None
        return {"action": action, **meta, "version": self.VERSION}

    def build(self, plan: dict[str, Any]) -> dict[str, Any]:
        action = plan.get("action")
        if not action:
            raise ValueError("Plan action is required.")
        parameters = plan.get("parameters") or {}
        if not isinstance(parameters, dict):
            raise ValueError("Plan parameters must be an object.")
        steps = self._build_business_graph(action, parameters, plan)
        definition = self.get_definition(action)
        return {
            "success": True,
            "status": "playbook_ready",
            "version": self.VERSION,
            "definition": definition,
            "intent": plan.get("intent"),
            "action": action,
            "steps": steps,
            "summary": summarize_steps(steps),
            "requires_approval": any(s["requires_approval"] for s in steps),
            "risk": "high" if any(s["risk"] == "high" for s in steps) else "low",
            "execution": {
                "mode": "governed_sequential",
                "checkpointing": True,
                "resumable": True,
                "result_propagation": True,
            },
        }

    def _build_business_graph(self, action: str, parameters: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
        graph = {
            "lead_scoring": ["lead_scoring", "ai_sales_qualification", "revenue_opportunity"],
            "customer_retention": ["churn_detection", "customer_retention", "sales_follow_up"],
            "sales_follow_up": ["lead_scoring", "sales_follow_up"],
            "business_insights": ["business_insights"],
        }.get(action, [action])
        steps = []
        for position, step_action in enumerate(graph, 1):
            step_plan = dict(plan, action=step_action)
            step_parameters = dict(parameters)
            steps.append({
                "step_id": f"step_{position}",
                "position": position,
                "action": step_action,
                "parameters": step_parameters,
                "depends_on": [f"step_{position - 1}"] if position > 1 else [],
                "on_success": "continue",
                "on_failure": "stop",
                "risk": "high" if step_action in {"refund_request", "send_notification", "sales_follow_up"} else "low",
                "requires_approval": step_action in {"refund_request", "sales_follow_up"},
                "condition": "previous.success == true" if position > 1 else "always",
                "retry_policy": {"max_attempts": 2, "backoff_seconds": 1, "retry_on": ["transient_error"]},
                "result_mapping": {"previous_result": "previous_result", "workflow_steps": "workflow_context.steps"},
            })
            steps[-1]["confidence"] = step_plan.get("confidence", 1.0)
            steps[-1]["expected_result"] = plan.get("expected_result")
            steps[-1]["policy"] = {"approval_required": steps[-1]["requires_approval"], "fail_closed": True, "external_execution": False}
        return steps

    def _enrich_steps(self, steps: list[dict[str, Any]], plan: dict[str, Any]) -> list[dict[str, Any]]:
        enriched = []
        for step in steps:
            item = deepcopy(step)
            item["confidence"] = plan.get("confidence", 1.0)
            item["expected_result"] = plan.get("expected_result")
            item["policy"] = {
                "approval_required": bool(item.get("requires_approval")),
                "fail_closed": True,
                "external_execution": False,
            }
            enriched.append(item)
        return enriched


playbook_engine = PlaybookEngine()
