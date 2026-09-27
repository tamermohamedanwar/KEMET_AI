from __future__ import annotations

from typing import Any, Dict, Optional

from .central_gate import central_execution_gate
from app.core.security_policy import PolicyDenied, PolicyGrant, security_policy


class ExecutionBoundary:
    """Mandatory authorization boundary for externally authorized execution."""

    VERSION = "1.0"

    def authorize(
        self,
        plan: Optional[Dict[str, Any]],
        authorization: Optional[Dict[str, Any]],
        action: str,
        subject_id: Optional[Any] = None,
    ) -> Dict[str, Any]:
        security_grant = (plan or {}).get("security_policy_grant")
        if security_grant is not None:
            if not isinstance(security_grant, dict):
                return {"allowed": False, "error": "security_policy_grant_invalid"}
            try:
                expires_at = security_grant.get("expires_at")
                from datetime import datetime
                grant = PolicyGrant(
                    subject_id=str(security_grant.get("subject_id", "")),
                    organization_id=int(security_grant.get("organization_id")),
                    actions=tuple(str(item) for item in security_grant.get("actions", ())),
                    resources=tuple(str(item) for item in security_grant.get("resources", ())),
                    expires_at=datetime.fromisoformat(str(expires_at)) if expires_at else None,
                )
                security_policy.authorize(
                    grant=grant, subject_id=str(subject_id if subject_id is not None else ""),
                    organization_id=int((plan or {}).get("organization_id")),
                    action=action, resource=str((plan or {}).get("resource") or action),
                )
            except (PolicyDenied, TypeError, ValueError, OverflowError) as exc:
                return {"allowed": False, "error": "security_policy_denied", "detail": str(exc)}

        handoff = (authorization or {}).get("gate_handoff")
        if action == "shortform_candidate_selection" and not handoff:
            return {"allowed": False, "executed": False, "error": "gate_handoff_required"}
        if handoff:
            from app.core.central_gate_handoff import GateHandoff
            if isinstance(handoff, dict):
                handoff = GateHandoff(**handoff)
            execution_key = str((authorization or {}).get("execution_key") or "")
            context = (plan or {}).get("context_fingerprint")
            return central_execution_gate.authorize_with_handoff(
                plan=plan, authorization=authorization, handoff=handoff,
                action=action, execution_key=execution_key,
                context_fingerprint=context,
            )
        return central_execution_gate.authorize(
            plan=plan, authorization=authorization, action=action,
        )

    def require(
        self,
        plan: Optional[Dict[str, Any]],
        authorization: Optional[Dict[str, Any]],
        action: str,
        subject_id: Optional[Any] = None,
    ) -> Dict[str, Any]:
        result = self.authorize(
            plan=plan,
            authorization=authorization,
            action=action,
            subject_id=subject_id,
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
