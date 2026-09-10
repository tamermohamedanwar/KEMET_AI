from __future__ import annotations

from typing import Any, Dict, Optional

from .authorization import execution_authorization


class CentralExecutionGate:
    """
    Single security boundary for project execution.

    No execution is allowed unless:
    1. An authorization object exists.
    2. The authorization is cryptographically valid.
    3. The authorization matches the exact plan.
    4. The authorization matches the requested action.
    """

    VERSION = "1.0"

    def authorize(
        self,
        plan: Optional[Dict[str, Any]],
        authorization: Optional[Dict[str, Any]],
        action: str,
    ) -> Dict[str, Any]:

        if not plan:
            return {
                "allowed": False,
                "executed": False,
                "error": "execution_plan_required",
            }

        if not authorization:
            return {
                "allowed": False,
                "executed": False,
                "error": "execution_authorization_required",
            }

        verification = execution_authorization.verify(
            authorization=authorization,
            plan=plan,
            action=action,
        )

        if not verification.get("authorized"):
            return {
                "allowed": False,
                "executed": False,
                "error": verification.get(
                    "error",
                    "execution_authorization_denied",
                ),
                "verification": verification,
            }

        return {
            "allowed": True,
            "executed": False,
            "action": action,
            "plan_id": verification.get("plan_id"),
            "plan_hash": verification.get("plan_hash"),
            "approver_id": verification.get("approver_id"),
            "expires_at": verification.get("expires_at"),
            "verification": verification,
        }


central_execution_gate = CentralExecutionGate()
