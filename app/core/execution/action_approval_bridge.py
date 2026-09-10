from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from .authorization import execution_authorization


@dataclass
class ActionPlan:
    request: str
    decision: Any
    context: Any
    action: str = "review"
    status: str = "waiting_approval"
    approved: bool = False
    approver_id: Optional[int] = None
    executed: bool = False
    external_execution: bool = False
    database_mutation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ActionApprovalBridge:
    VERSION = "2.0"

    def build_plan(
        self,
        request: str,
        decision: Any,
        context: Any,
    ) -> Dict[str, Any]:
        plan = ActionPlan(
            request=request,
            decision=decision,
            context=context,
        )

        plan_dict = plan.to_dict()

        return {
            "success": True,
            "status": "waiting_approval",
            "plan": plan_dict,
            "approval": {
                "required": True,
                "status": "waiting_approval",
                "approved": False,
            },
            "execution": {
                "allowed": False,
                "external_execution": False,
                "database_mutation": False,
                "executed": False,
            },
        }

    def approve_and_prepare(
        self,
        plan: Dict[str, Any],
        approved: bool = False,
        approver_id: Optional[int] = None,
    ) -> Dict[str, Any]:

        if not approved:
            return {
                "success": True,
                "status": "waiting_approval",
                "plan": plan,
                "approved": False,
                "approver_id": approver_id,
                "executed": False,
                "external_execution": False,
                "database_mutation": False,
                "execution": {
                    "allowed": False,
                    "executed": False,
                    "external_execution": False,
                    "database_mutation": False,
                },
            }

        prepared_plan = dict(plan)

        prepared_plan["status"] = "approved"
        prepared_plan["approved"] = True
        prepared_plan["approver_id"] = approver_id
        prepared_plan["executed"] = False
        prepared_plan["external_execution"] = False
        prepared_plan["database_mutation"] = False

        authorization = execution_authorization.create_authorization(
            prepared_plan,
            approver_id=approver_id,
        )

        prepared_plan["plan_id"] = authorization["plan_id"]
        prepared_plan["plan_hash"] = authorization["plan_hash"]

        return {
            "success": True,
            "status": "approved",
            "plan": prepared_plan,
            "approved": True,
            "approver_id": approver_id,
            "executed": False,
            "external_execution": False,
            "database_mutation": False,
            "authorization": authorization,
            "execution": {
                "allowed": True,
                "executed": False,
                "external_execution": False,
                "database_mutation": False,
                "authorization_required": True,
            },
        }

    def verify_execution(
        self,
        plan: Dict[str, Any],
        authorization: Optional[Dict[str, Any]],
        action: str,
    ) -> Dict[str, Any]:
        return execution_authorization.verify(
            authorization=authorization,
            plan=plan,
            action=action,
        )
