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
        execution_envelope_payload: Optional[Dict[str, Any]] = None,
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
            steps = plan.get("steps") or []
            if isinstance(steps, list) and steps:
                action = str((steps[0] or {}).get("action") or "").strip()

        if not action:
            return {
                "success": False,
                "status": "blocked",
                "executed": False,
                "error": "execution_action_required",
            }

        if not isinstance(authorization, dict):
            return {
                "success": False,
                "status": "blocked",
                "executed": False,
                "error": "execution_authorization_required",
            }

        envelope = execution_envelope_payload or plan.get("execution_envelope")
        if envelope or plan.get("approval_package_hash") or plan.get("central_gate_handoff_hash"):
            from app.core.federation.execution_envelope import execution_envelope
            provider_id = str(plan.get("provider_id") or "kemet")
            execution_key = str(plan.get("execution_key") or authorization.get("execution_key") or plan.get("plan_id") or "")
            if not isinstance(envelope, dict) or not execution_envelope.verify(
                envelope,
                authorization=authorization,
                execution_key=execution_key,
                provider_id=provider_id,
                action=action,
                approval_package_hash=str(plan.get("approval_package_hash") or "") or None,
                decision_hash=str(plan.get("decision_hash") or "") or None,
                handoff_hash=str(plan.get("central_gate_handoff_hash") or "") or None,
                evidence_context_hash=str(plan.get("evidence_context_hash") or "") or None,
                outcome_contract_digest=str(plan.get("outcome_contract_digest") or "") or None,
                artifact_preview_digest=str(plan.get("artifact_preview_digest") or "") or None,
            ):
                return {"success": False, "status": "blocked", "executed": False,
                        "error": "execution_envelope_invalid", "action": action}

        parameters = dict(plan.get("parameters") or {})
        execution_parameters = authorization.get("execution_parameters") or {}
        if execution_parameters:
            if not isinstance(execution_parameters, dict):
                return {
                    "success": False,
                    "status": "blocked",
                    "executed": False,
                    "error": "execution_parameters_invalid",
                    "action": action,
                }
            parameters.update(execution_parameters)

        if not isinstance(parameters, dict):
            return {
                "success": False,
                "status": "failed",
                "executed": False,
                "error": "execution_parameters_invalid",
                "action": action,
            }

        gate_kwargs = {
            "plan": plan,
            "authorization": authorization,
            "action": action,
        }
        if plan.get("security_policy_grant") is not None:
            gate_kwargs["subject_id"] = user_id
        gate_result = execution_boundary.require(**gate_kwargs)

        if not gate_result.get("allowed"):
            return {
                **gate_result,
                "success": False,
                "status": "blocked",
                "executed": False,
            }

        if not action_registry.exists(action):
            return {
                "success": False,
                "status": "failed",
                "executed": False,
                "error": "unknown_execution_action",
                "action": action,
            }

        # Consume the one-time authorization immediately before
        # entering the actual action execution boundary.
        authorization_context = dict(authorization)
        authorization_context["_execution_plan"] = plan
        authorization_context["_execution_action"] = action
        if not execution_authorization.consume(authorization_context):
            return {
                "success": False,
                "status": "blocked",
                "executed": False,
                "error": "execution_authorization_used",
                "action": action,
            }

        try:
            parameters["_execution_authorization"] = authorization
            parameters["_execution_plan"] = plan
            parameters["_execution_action"] = action
            parameters["_approved_execution"] = True
            result = action_registry.execute(
                action,
                parameters,
                user_id=user_id,
            )
        except Exception as exc:
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
            if action in {"whatsapp_send_text", "whatsapp_send_template"} and result.get("provider_message_id"):
                from app.core.execution_evidence import execution_evidence
                execution_key = str(plan.get("execution_key") or authorization.get("execution_key") or plan.get("plan_id") or "")
                execution_evidence.record(
                    organization_id=int(plan.get("organization_id") or authorization.get("organization_id") or 0),
                    execution_key=execution_key,
                    job_id=plan.get("job_id"),
                    stage="channel.delivery", status="sent",
                    evidence_key=f"{execution_key}:whatsapp:{result['provider_message_id']}:sent",
                    receipt={"provider": "meta_whatsapp_cloud", "message_id": result["provider_message_id"],
                             "delivery_status": "sent", "operation": action},
                )
            if action == "bosta_create_delivery" and (result.get("order_id") or result.get("tracking_number")):
                from app.core.execution_evidence import execution_evidence
                execution_key = str(plan.get("execution_key") or authorization.get("execution_key") or plan.get("plan_id") or "")
                execution_evidence.record(
                    organization_id=int(plan.get("organization_id") or authorization.get("organization_id") or 0),
                    execution_key=execution_key, job_id=plan.get("job_id"),
                    stage="fulfillment.created", status="completed",
                    evidence_key=f"{execution_key}:bosta:created:{result.get('order_id') or result.get('tracking_number')}",
                    receipt={"provider": "bosta_api", "order_id": result.get("order_id"),
                             "tracking_number": result.get("tracking_number"), "business_reference": result.get("business_reference")},
                )
            result_status = str(result.get("status") or "").strip()
            terminal_statuses = {"completed", "failed", "blocked", "cancelled", "idempotent_replay_blocked", "deadline_exceeded"}
            execution_status = str(
                result.get("execution_status")
                or ("completed" if result.get("success") is True else result_status if result_status in terminal_statuses else "failed")
            )
            return {
                **result,
                "action": action,
                "executed": bool(result.get("executed", True)),
                "execution_status": execution_status,
                "business_status": result.get("status"),
                "runtime": "canonical",
                "runtime_version": self.VERSION,
            }

        return {
            "success": True,
            "action": action,
            "result": result,
            "executed": True,
            "execution_status": "completed",
            "business_status": result.get("status") if isinstance(result, dict) else None,
            "runtime": "canonical",
            "runtime_version": self.VERSION,
        }


canonical_execution_runtime = CanonicalExecutionRuntime()
