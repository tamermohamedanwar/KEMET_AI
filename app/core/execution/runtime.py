from __future__ import annotations

from typing import Any, Dict, Optional

from .execution_boundary import execution_boundary
from .authorization import execution_authorization
from app.core.audit.event import AuditEvent
from app.core.audit.service import persist_audit_event


def _audit_event(
    *,
    event_type,
    action=None,
    status="recorded",
    actor_id=None,
    organization_id=None,
    metadata=None,
):
    event = AuditEvent(
        event_type=event_type,
        actor_type="user" if actor_id is not None else "system",
        actor_id=str(actor_id) if actor_id is not None else None,
        organization_id=organization_id,
        action=action,
        status=status,
        metadata=metadata or {},
    )

    try:
        persist_audit_event(event)
    except Exception:
        # Audit failure must never bypass or alter execution governance.
        pass

    return event


class CanonicalExecutionRuntime:
    """
    Canonical execution path for Kemet AI.

    Intent
        -> Plan
        -> Authorization
        -> Execution Boundary
        -> Action Registry
        -> Result

    The runtime composes the existing security primitives.
    It does not replace them.
    """

    VERSION = "1.1"

    def execute(
        self,
        *,
        plan: Dict[str, Any],
        authorization: Optional[Dict[str, Any]],
        action_registry,
        user_id: Optional[Any] = None,
    ) -> Dict[str, Any]:

        if not isinstance(plan, dict):
            return {
                "success": False,
                "status": "blocked",
                "executed": False,
                "error": "execution_plan_required",
            }

        action = str(
            plan.get("action")
            or plan.get("command")
            or ""
        ).strip()

        if not action:
            return {
                "success": False,
                "status": "blocked",
                "executed": False,
                "error": "execution_action_required",
            }

        if not isinstance(authorization, dict):
            _audit_event(
                event_type="execution.authorization_required",
                action=action,
                status="blocked",
                actor_id=user_id,
                organization_id=plan.get("organization_id"),
                metadata={
                    "governance": "1.0",
                    "runtime": "canonical",
                    "policy": "authorization_required",
                    "executed": False,
                },
            )
            return {
                "success": False,
                "status": "blocked",
                "executed": False,
                "error": "execution_authorization_required",
            }

        parameters = plan.get("parameters") or {}

        if not isinstance(parameters, dict):
            return {
                "success": False,
                "status": "failed",
                "executed": False,
                "error": "execution_parameters_invalid",
                "action": action,
            }

        gate_result = execution_boundary.require(
            plan=plan,
            authorization=authorization,
            action=action,
        )

        if not gate_result.get("allowed"):
            _audit_event(
                event_type="execution.gate_blocked",
                action=action,
                status="blocked",
                actor_id=user_id,
                organization_id=plan.get("organization_id"),
                metadata={
                    "governance": "1.0",
                    "runtime": "canonical",
                    "policy": "central_gate_blocked",
                    "error": gate_result.get("error"),
                    "plan_id": gate_result.get("plan_id"),
                    "plan_hash": gate_result.get("plan_hash"),
                    "executed": False,
                },
            )
            return {
                **gate_result,
                "success": False,
                "status": "blocked",
                "executed": False,
            }

        if not action_registry.exists(action):
            _audit_event(
                event_type="execution.unknown_action",
                action=action,
                status="failed",
                actor_id=user_id,
                organization_id=plan.get("organization_id"),
                metadata={
                    "governance": "1.0",
                    "runtime": "canonical",
                    "policy": "unknown_action",
                    "executed": False,
                },
            )
            return {
                "success": False,
                "status": "failed",
                "executed": False,
                "error": "unknown_execution_action",
                "action": action,
            }

        # Consume the one-time authorization immediately before
        # entering the actual action execution boundary.
        authorization_context = dict(authorization or {})
        authorization_context["_execution_plan"] = plan
        authorization_context["_execution_action"] = action
        if not execution_authorization.consume(authorization_context):
            _audit_event(
                event_type="execution.authorization_replay",
                action=action,
                status="blocked",
                actor_id=user_id,
                organization_id=plan.get("organization_id"),
                metadata={
                    "governance": "1.0",
                    "runtime": "canonical",
                    "policy": "authorization_replay_blocked",
                    "executed": False,
                },
            )
            return {
                "success": False,
                "status": "blocked",
                "executed": False,
                "error": "execution_authorization_used",
                "action": action,
            }

        try:
            result = action_registry.execute(
                action,
                parameters,
                user_id=user_id,
            )
        except Exception as exc:
            _audit_event(
                event_type="execution.failed",
                action=action,
                status="failed",
                actor_id=user_id,
                organization_id=plan.get("organization_id"),
                metadata={
                    "governance": "1.0",
                    "runtime": "canonical",
                    "policy": "authorized",
                    "executed": True,
                    "error": str(exc),
                },
            )
            return {
                "success": False,
                "status": "failed",
                "executed": True,
                "error": str(exc),
                "action": action,
                "runtime": "canonical",
                "runtime_version": self.VERSION,
            }

        if isinstance(result, dict):
            _audit_event(
                event_type="execution.completed",
                action=action,
                status="completed" if result.get("success", False) else "failed",
                actor_id=user_id,
                organization_id=plan.get("organization_id"),
                metadata={
                    "governance": "1.0",
                    "runtime": "canonical",
                    "policy": "authorized",
                    "executed": True,
                    "success": bool(result.get("success", False)),
                },
            )
            return {
                **result,
                "action": action,
                "executed": True,
                "runtime": "canonical",
                "runtime_version": self.VERSION,
            }

        _audit_event(
            event_type="execution.completed",
            action=action,
            status="completed",
            actor_id=user_id,
            organization_id=plan.get("organization_id"),
            metadata={
                "governance": "1.0",
                "runtime": "canonical",
                "policy": "authorized",
                "executed": True,
                "success": True,
            },
        )

        return {
            "success": True,
            "action": action,
            "result": result,
            "executed": True,
            "runtime": "canonical",
            "runtime_version": self.VERSION,
        }


canonical_execution_runtime = CanonicalExecutionRuntime()
