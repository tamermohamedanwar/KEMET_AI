from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from app.core.central_gate_handoff import GateHandoff, verify_gate_handoff
from .authorization import execution_authorization


class CentralExecutionGate:
    """Single security boundary for governed project execution."""

    VERSION = "1.2"

    def authorize(
        self,
        plan: Optional[Dict[str, Any]],
        authorization: Optional[Dict[str, Any]],
        action: str,
    ) -> Dict[str, Any]:
        if not plan:
            return {"allowed": False, "executed": False, "error": "execution_plan_required"}
        if not authorization:
            return {"allowed": False, "executed": False, "error": "execution_authorization_required"}
        verification = execution_authorization.verify(
            authorization=authorization,
            plan=plan,
            action=action,
        )
        if not verification.get("authorized"):
            return {
                "allowed": False,
                "executed": False,
                "error": verification.get("error", "execution_authorization_denied"),
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

    def authorize_with_handoff(
        self,
        plan: Optional[Dict[str, Any]],
        authorization: Optional[Dict[str, Any]],
        handoff: Optional[GateHandoff],
        action: str,
        execution_key: str,
        context_fingerprint: Optional[str] = None,
    ) -> Dict[str, Any]:
        if handoff is None:
            return {"allowed": False, "executed": False, "error": "gate_handoff_required"}
        if not plan:
            return {"allowed": False, "executed": False, "error": "execution_plan_required"}
        expected_org = plan.get("organization_id")
        if expected_org is not None and handoff.organization_id != expected_org:
            return {"allowed": False, "executed": False, "error": "gate_tenant_mismatch"}
        expected_context = context_fingerprint or plan.get("context_fingerprint")
        if not expected_context and isinstance(plan.get("context"), dict):
            expected_context = hashlib.sha256(
                json.dumps(plan["context"], sort_keys=True, default=str).encode()
            ).hexdigest()
        if expected_context and handoff.context_fingerprint != expected_context:
            return {"allowed": False, "executed": False, "error": "gate_context_mismatch"}
        expected_hash = execution_authorization.plan_hash(plan)
        if expected_hash != handoff.plan_hash:
            return {"allowed": False, "executed": False, "error": "gate_plan_mismatch"}
        if not verify_gate_handoff(
            handoff,
            organization_id=handoff.organization_id,
            plan_hash=expected_hash,
            action=action,
            execution_key=execution_key,
        ):
            return {"allowed": False, "executed": False, "error": "gate_handoff_invalid"}
        if not authorization:
            return {"allowed": False, "executed": False, "error": "execution_authorization_required"}
        result = self.authorize(plan, authorization, action)
        if not result.get("allowed"):
            return result
        if result.get("approver_id") != handoff.approver_id:
            return {"allowed": False, "executed": False, "error": "gate_approver_mismatch"}
        if str(authorization.get("execution_key") or "") != execution_key:
            return {"allowed": False, "executed": False, "error": "gate_execution_key_mismatch"}
        if str(authorization.get("authorization_source") or "") == "human_approval":
            if str(authorization.get("handoff_hash") or "") != handoff.handoff_hash:
                return {"allowed": False, "executed": False, "error": "gate_authorization_handoff_mismatch"}
        return {**result, "handoff_hash": handoff.handoff_hash, "execution_key": execution_key}


central_execution_gate = CentralExecutionGate()
