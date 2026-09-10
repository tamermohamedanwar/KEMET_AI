from __future__ import annotations

from typing import Any, Dict

from app.core.execution.authorization import execution_authorization
from app.core.execution.runtime import canonical_execution_runtime
from app.core.execution.risk_policy import execution_risk_policy
from app.core.evidence import execution_evidence_fabric
from app.services.entitlement_service import EntitlementService


class GovernedExecutionService:
    """Canonical governance entry point for automation execution."""

    VERSION = "1.1"

    DIRECT_SAFE_ACTIONS = {
        "business_insights", "revenue_autopilot_plan", "order_tracking",
        "lead_scoring", "churn_detection", "revenue_opportunity",
        "ai_sales_qualification",
    }

    APPROVAL_REQUIRED_ACTIONS = {
        "refund_request", "revenue_autopilot_run", "sales_follow_up",
        "send_notification", "create_ticket", "customer_retention",
        "payment_issue", "account_help", "smart_ticket_ai",
    }

    def _policy(self, action: str) -> str:
        if action in self.DIRECT_SAFE_ACTIONS:
            return "direct_safe"
        if action in self.APPROVAL_REQUIRED_ACTIONS:
            return "approval_required"
        return "blocked"

    def _risk(self, action: str, policy: str) -> dict[str, Any]:
        return execution_risk_policy.controls(action, policy)

    def execute(
        self, *, action: str, parameters: Dict[str, Any] | None = None,
        data: Dict[str, Any] | None = None, organization_id: int | None = None,
        user_id: int | None = None,
    ) -> Dict[str, Any]:
        action = str(action or "").strip()
        parameters = dict(parameters or {})
        data = dict(data or {})

        if organization_id is None:
            return {"success": False, "status": "blocked",
                    "error": "organization_id_required", "governance": self.VERSION,
                    "executed": False}

        entitlement = EntitlementService.require_feature(organization_id, "automation")
        if not entitlement.get("allowed"):
            return {"success": False, "status": "blocked",
                    "error": "automation_feature_not_available",
                    "plan": entitlement.get("plan"), "feature": entitlement.get("feature"),
                    "governance": self.VERSION, "executed": False}

        policy = self._policy(action)
        risk = self._risk(action, policy)

        if policy == "approval_required":
            return {"success": False, "status": "waiting_approval", "action": action,
                    "approval_required": True, "requires_human": True,
                    "financial_action_executed": False, "external_execution": False,
                    "database_mutation": False, "governance": self.VERSION,
                    "policy": policy, "risk": risk, "executed": False}

        if policy != "direct_safe":
            return {"success": False, "status": "blocked", "error": "action_not_governed",
                    "action": action, "governance": self.VERSION, "policy": policy,
                    "risk": risk, "executed": False}

        plan = {
            "request": "governed_automation", "decision": "policy_authorized",
            "context": {"organization_id": organization_id, "user_id": user_id},
            "action": action, "status": "authorized", "approved": False,
            "approver_id": None, "executed": False, "external_execution": False,
            "database_mutation": False, "governance_policy": "direct_safe",
            "risk": risk, "parameters": parameters, "data": data,
        }

        authorization = execution_authorization.create_policy_authorization(
            plan, policy="direct_safe"
        )
        if not authorization.get("authorized"):
            return {"success": False, "status": "blocked",
                    "error": authorization.get("error", "governance_authorization_failed"),
                    "action": action, "governance": self.VERSION,
                    "risk": risk, "executed": False}

        canonical_plan = dict(plan)
        canonical_plan.update({
            "plan_id": authorization["plan_id"],
            "plan_hash": authorization["plan_hash"],
            "authorization_source": authorization.get("authorization_source"),
            "governance_policy": authorization.get("governance_policy"),
        })

        result = canonical_execution_runtime.execute(
            plan=canonical_plan, authorization=authorization,
            action_registry=self._registry(), user_id=user_id,
        )
        evidence = execution_evidence_fabric.execution_record(
            action=action,
            plan_hash=canonical_plan.get("plan_hash"),
            risk=risk,
            result=result,
        )
        return {
            **result,
            "governance": self.VERSION,
            "policy": policy,
            "risk": risk,
            "evidence": evidence,
        }

    @staticmethod
    def _registry():
        from app.automation.action_registry import registry
        return registry


governed_execution_service = GovernedExecutionService()
