from __future__ import annotations

from typing import Any, Dict, Optional

from .central_gate import central_execution_gate


class ExecutionBoundary:
    """Mandatory authorization boundary for externally authorized execution."""

    VERSION = "1.0"

    def authorize(
        self,
        plan: Optional[Dict[str, Any]],
        authorization: Optional[Dict[str, Any]],
        action: str,
    ) -> Dict[str, Any]:
        return central_execution_gate.authorize(
            plan=plan,
            authorization=authorization,
            action=action,
        )

    def require(
        self,
        plan: Optional[Dict[str, Any]],
        authorization: Optional[Dict[str, Any]],
        action: str,
    ) -> Dict[str, Any]:
        result = self.authorize(
            plan=plan,
            authorization=authorization,
            action=action,
        )

        if not result.get("allowed"):
            return {
                **result,
                "executed": False,
                "status": "blocked",
            }

        return {
            **result,
            "status": "authorized",
            "executed": False,
        }


execution_boundary = ExecutionBoundary()
