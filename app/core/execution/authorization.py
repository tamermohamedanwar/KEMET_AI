from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dotenv import load_dotenv
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.core.execution_authorization_store import execution_authorization_store


load_dotenv(".env.agent", override=False)

TOKEN_TTL_SECONDS = 300


@dataclass(frozen=True)
class ExecutionAuthorization:
    token: str
    plan_id: str
    plan_hash: str
    action: str
    approver_id: Optional[int]
    expires_at: int


class ExecutionAuthorizationService:
    """
    Central authorization layer for execution.

    Authentication and execution authorization are separate concerns.
    A valid agent authentication token alone must never authorize execution.
    """

    def __init__(self) -> None:
        self.secret = os.getenv("KEMET_EXECUTION_SECRET", "")

    def _canonical_plan(self, plan: Dict[str, Any]) -> str:
        excluded_keys = {
            "approved",
            "approver_id",
            "executed",
            "execution_token",
            "approval",
            "execution",
            "plan_hash",
            "authorization",
            "_approved_execution",
            "execution_envelope",
            "approval_package_hash",
            "approval_decision_hash",
            "central_gate_handoff_hash",
        }

        def sanitize(value):
            if isinstance(value, dict):
                return {
                    key: sanitize(item)
                    for key, item in value.items()
                    if key not in excluded_keys
                }

            if isinstance(value, list):
                return [sanitize(item) for item in value]

            return value

        clean = sanitize(dict(plan))
        if {"task_id", "organization_id", "task_type", "risk", "steps"}.issubset(clean):
            from dataclasses import asdict
            from app.core.task_planner import PlannedStep
            normalized_steps = []
            for item in clean.get("steps") or []:
                if not isinstance(item, dict):
                    normalized_steps.append(item)
                    continue
                normalized_steps.append(
                    asdict(
                        PlannedStep(
                            step_id=str(item.get("step_id") or ""),
                            objective=str(item.get("objective") or ""),
                            action=str(item.get("action") or ""),
                            risk=str(item.get("risk") or ""),
                            requires_approval=bool(item.get("requires_approval")),
                            depends_on=tuple(item.get("depends_on") or ()),
                            capabilities=frozenset(item.get("capabilities") or ()),
                            parameters=dict(item.get("parameters") or {}),
                        )
                    )
                )
            clean = {
                "task_id": clean.get("task_id"),
                "organization_id": clean.get("organization_id"),
                "task_type": clean.get("task_type"),
                "risk": clean.get("risk"),
                "steps": normalized_steps,
            }

        return json.dumps(
            clean,
            sort_keys=True,
            default=str,
            ensure_ascii=False,
        )

    def plan_hash(self, plan: Dict[str, Any]) -> str:
        payload = self._canonical_plan(plan).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _token_payload(
        self,
        plan_id: str,
        plan_hash: str,
        action: str,
        approver_id: Optional[int],
        expires_at: int,
        authorization_source: Optional[str] = None,
        nonce: Optional[str] = None,
        handoff_hash: Optional[str] = None,
    ) -> str:
        base = (
            f"{plan_id}:"
            f"{plan_hash}:"
            f"{action}:"
            f"{approver_id}:"
            f"{expires_at}"
        )

        if authorization_source == "governance_policy":
            base = f"{base}:governance_policy"
        if nonce:
            base = f"{base}:{nonce}"
        if handoff_hash:
            base = f"{base}:handoff:{handoff_hash}"
        return base

    def create_authorization(
        self,
        plan: Dict[str, Any],
        approver_id: Optional[int],
    ) -> Dict[str, Any]:

        if not self.secret:
            raise RuntimeError("execution_secret_not_configured")

        prepared_plan = dict(plan)

        plan_id = str(
            prepared_plan.get("plan_id")
            or prepared_plan.get("id")
            or secrets.token_hex(12)
        )

        prepared_plan["plan_id"] = plan_id

        action = str(prepared_plan.get("action") or "").strip()
        if not action:
            steps = prepared_plan.get("steps") or []
            if isinstance(steps, list) and steps:
                action = str((steps[0] or {}).get("action") or "").strip()
        action = action or "unknown"

        digest = self.plan_hash(prepared_plan)

        expires_at = int(time.time()) + TOKEN_TTL_SECONDS
        nonce = secrets.token_hex(16)

        payload = self._token_payload(
            plan_id,
            digest,
            action,
            approver_id,
            expires_at,
            nonce=nonce,
        )

        token = hmac.new(
            self.secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "authorized": True,
            "token": token,
            "plan_id": plan_id,
            "plan_hash": digest,
            "action": action,
            "approver_id": approver_id,
            "expires_at": expires_at,
            "one_time": True,
            "nonce": nonce,
        }

    def create_handoff_authorization(
        self,
        plan: Dict[str, Any],
        handoff: Any,
    ) -> Dict[str, Any]:
        if not isinstance(plan, dict):
            return {"authorized": False, "error": "execution_plan_required"}
        if handoff is None:
            return {"authorized": False, "error": "gate_handoff_required"}
        from app.core.central_gate_handoff import verify_gate_handoff

        action = str(getattr(handoff, "action", "") or "").strip()
        execution_key = str(getattr(handoff, "execution_key", "") or "").strip()
        handoff_hash = str(getattr(handoff, "handoff_hash", "") or "").strip()
        organization_id = getattr(handoff, "organization_id", None)
        if not action or not execution_key or not handoff_hash:
            return {"authorized": False, "error": "gate_handoff_binding_required"}
        if organization_id is None or int(plan.get("organization_id") or 0) != int(organization_id):
            return {"authorized": False, "error": "gate_tenant_mismatch"}
        expected_hash = self.plan_hash(plan)
        if expected_hash != str(getattr(handoff, "plan_hash", "") or ""):
            return {"authorized": False, "error": "gate_plan_mismatch"}
        if not verify_gate_handoff(
            handoff,
            organization_id=int(organization_id),
            plan_hash=expected_hash,
            action=action,
            execution_key=execution_key,
        ):
            return {"authorized": False, "error": "gate_handoff_invalid"}
        if not self.secret:
            return {"authorized": False, "error": "execution_secret_not_configured"}

        approver_id = int(getattr(handoff, "approver_id", 0) or 0)
        expires_at = int(time.time()) + TOKEN_TTL_SECONDS
        nonce = secrets.token_hex(16)
        plan_id = str(plan.get("plan_id") or plan.get("task_id") or plan.get("id") or secrets.token_hex(12))
        prepared_plan = dict(plan)
        prepared_plan["plan_id"] = plan_id
        digest = self.plan_hash(prepared_plan)
        if digest != expected_hash:
            return {"authorized": False, "error": "gate_plan_id_binding_mismatch"}
        payload = self._token_payload(
            plan_id, digest, action, approver_id, expires_at,
            nonce=nonce, handoff_hash=handoff_hash,
        )
        token = hmac.new(
            self.secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return {
            "authorized": True,
            "token": token,
            "plan_id": plan_id,
            "plan_hash": digest,
            "action": action,
            "approver_id": approver_id,
            "expires_at": expires_at,
            "one_time": True,
            "nonce": nonce,
            "execution_key": execution_key,
            "handoff_hash": handoff_hash,
            "authorization_source": "human_approval",
        }

    def create_policy_authorization(
        self,
        plan: Dict[str, Any],
        policy: str,
    ) -> Dict[str, Any]:
        """
        Issue a short-lived authorization for an explicitly governed
        machine policy. This is intentionally separate from human approval.
        """
        if not isinstance(plan, dict):
            return {
                "authorized": False,
                "error": "execution_plan_required",
            }

        if not policy:
            return {
                "authorized": False,
                "error": "governance_policy_required",
            }

        if not self.secret:
            return {
                "authorized": False,
                "error": "execution_secret_not_configured",
            }

        prepared_plan = dict(plan)
        prepared_plan["governance_policy"] = policy
        prepared_plan["authorization_source"] = "governance_policy"

        plan_id = str(prepared_plan.get("plan_id") or "")
        if not plan_id:
            plan_id = secrets.token_hex(16)
            prepared_plan["plan_id"] = plan_id

        action = str(prepared_plan.get("action") or "").strip()
        if not action:
            return {
                "authorized": False,
                "error": "execution_action_required",
            }

        digest = self.plan_hash(prepared_plan)
        expires_at = int(time.time()) + TOKEN_TTL_SECONDS
        nonce = secrets.token_hex(16)

        payload = self._token_payload(
            plan_id,
            digest,
            action,
            None,
            expires_at,
            authorization_source="governance_policy",
            nonce=nonce,
        )

        token = hmac.new(
            self.secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "authorized": True,
            "token": token,
            "plan_id": plan_id,
            "plan_hash": digest,
            "action": action,
            "approver_id": None,
            "expires_at": expires_at,
            "one_time": True,
            "authorization_source": "governance_policy",
            "governance_policy": policy,
            "nonce": nonce,
        }

    def verify(
        self,
        authorization: Optional[Dict[str, Any]],
        plan: Dict[str, Any],
        action: str,
    ) -> Dict[str, Any]:

        if not authorization:
            return {
                "authorized": False,
                "error": "execution_authorization_required",
            }

        if not self.secret:
            return {
                "authorized": False,
                "error": "execution_secret_not_configured",
            }

        token = str(
            authorization.get("token") or ""
        )

        if not token:
            return {
                "authorized": False,
                "error": "execution_token_required",
            }

        try:
            expires_at = int(
                authorization.get("expires_at") or 0
            )
        except (TypeError, ValueError):
            return {
                "authorized": False,
                "error": "execution_expiry_invalid",
            }

        if expires_at <= int(time.time()):
            return {
                "authorized": False,
                "error": "execution_authorization_expired",
            }

        plan_id = str(
            authorization.get("plan_id") or ""
        )

        if not plan_id:
            return {
                "authorized": False,
                "error": "execution_plan_id_required",
            }

        plan_with_id = dict(plan)
        plan_with_id["plan_id"] = plan_id

        expected_hash = self.plan_hash(
            plan_with_id
        )

        supplied_hash = str(
            authorization.get("plan_hash") or ""
        )

        if not supplied_hash:
            return {
                "authorized": False,
                "error": "execution_plan_hash_required",
            }

        if not hmac.compare_digest(
            expected_hash,
            supplied_hash,
        ):
            return {
                "authorized": False,
                "error": "execution_plan_mismatch",
            }

        supplied_action = str(
            authorization.get("action") or ""
        )

        if supplied_action != str(action):
            return {
                "authorized": False,
                "error": "execution_action_mismatch",
            }

        approver_id = authorization.get(
            "approver_id"
        )

        authorization_source = str(
            authorization.get("authorization_source") or ""
        ).strip()

        if authorization_source == "human_approval":
            handoff_hash = str(authorization.get("handoff_hash") or "").strip()
            if not handoff_hash:
                return {
                    "authorized": False,
                    "error": "handoff_hash_required",
                }

        if authorization_source == "human_approval":
            if not str(authorization.get("handoff_hash") or "").strip():
                return {
                    "authorized": False,
                    "error": "handoff_hash_required",
                }
            if not str(authorization.get("execution_key") or "").strip():
                return {
                    "authorized": False,
                    "error": "execution_key_required",
                }

        elif authorization_source == "governance_policy":
            governance_policy = str(
                authorization.get("governance_policy") or ""
            ).strip()

            if not governance_policy:
                return {
                    "authorized": False,
                    "error": "governance_policy_required",
                }

            if str(plan_with_id.get("authorization_source") or "") != "governance_policy":
                return {
                    "authorized": False,
                    "error": "governance_authorization_source_mismatch",
                }

            if str(plan_with_id.get("governance_policy") or "") != governance_policy:
                return {
                    "authorized": False,
                    "error": "governance_policy_mismatch",
                }

        elif authorization_source:
            return {
                "authorized": False,
                "error": "execution_authorization_source_invalid",
            }

        payload = self._token_payload(
            plan_id,
            supplied_hash,
            supplied_action,
            approver_id,
            expires_at,
            authorization_source=authorization_source or None,
            nonce=str(authorization.get("nonce") or "") or None,
            handoff_hash=str(authorization.get("handoff_hash") or "") or None,
        )

        expected_token = hmac.new(
            self.secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            expected_token,
            token,
        ):
            return {
                "authorized": False,
                "error": "execution_token_invalid",
            }

        result = {
            "authorized": True,
            "plan_id": plan_id,
            "plan_hash": supplied_hash,
            "action": supplied_action,
            "approver_id": approver_id,
            "expires_at": expires_at,
            "one_time": True,
        }

        if authorization_source == "governance_policy":
            result["authorization_source"] = "governance_policy"
            result["governance_policy"] = str(
                authorization.get("governance_policy") or ""
            )

        return result


    def consume(
        self,
        authorization: Optional[Dict[str, Any]],
        *,
        plan: Optional[Dict[str, Any]] = None,
        action: Optional[str] = None,
    ) -> bool:
        if not isinstance(authorization, dict):
            return False
        context = dict(authorization)
        if plan is not None:
            context["_execution_plan"] = plan
        if action is not None:
            context["_execution_action"] = action
        return execution_authorization_store.consume(
            context, plan=plan, action=action
        )

execution_authorization = ExecutionAuthorizationService()
