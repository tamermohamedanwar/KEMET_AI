from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Mapping

import requests

from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.integration.connector_contract import ConnectorContract
from app.core.integration.connector_registry import connector_registry
from app.core.secret_boundary import redact, resolve_secret, secret_reference


class SallaConnectorService:
    VERSION = "1.0"
    PROVIDER = "salla_api"
    BASE_URL = "https://api.salla.dev/admin/v2"
    OPERATIONS = ("get_order", "update_order")
    WEBHOOK_HEADER_ENV = "KEMET_SALLA_WEBHOOK_HEADER"
    WEBHOOK_SECRET_ENV = "KEMET_SALLA_WEBHOOK_SECRET"

    def contract(self, organization_id: int) -> ConnectorContract:
        return ConnectorContract(
            connector_id=self.PROVIDER, version=self.VERSION, organization_id=int(organization_id),
            operations=self.OPERATIONS, data_scopes=("store", "order", "product", "customer", "webhook"),
            risk_tier="high", approval_level="human", idempotency="required",
            timeout_seconds=30, max_retries=0, reversible=False, evidence_required=True,
        )

    def register(self, organization_id: int) -> dict[str, Any]:
        return connector_registry.register(self.contract(int(organization_id)))

    @staticmethod
    def _target(path: str) -> str:
        target = f"{SallaConnectorService.BASE_URL}/{str(path).lstrip('/')}"
        validate_public_http_target(target)
        return target

    @staticmethod
    def idempotency_key(*, organization_id: int, event: str, external_id: str) -> str:
        raw = f"salla:{int(organization_id)}:{str(event).strip()}:{str(external_id).strip()}".encode()
        return hashlib.sha256(raw).hexdigest()

    def plan_get_order(self, *, organization_id: int, order_id: str) -> dict[str, Any]:
        if not organization_id or not str(order_id).strip():
            raise ValueError("order_identity_required")
        self.register(int(organization_id))
        return redact({
            "success": True, "status": "proposal", "provider": self.PROVIDER,
            "operation": "get_order", "organization_id": int(organization_id),
            "endpoint": self._target(f"orders/{str(order_id).strip()}"),
            "idempotency_key": self.idempotency_key(organization_id=organization_id, event="order.read", external_id=order_id),
            "secret_reference": secret_reference(self.PROVIDER, "access_token"),
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False,
                           "auto_execute": False, "human_approval_required": False, "canonical_executor": "kemet"},
        })

    def execute_update_order(self, *, organization_id: int, order_id: str,
                             updates: Mapping[str, Any],
                             approved_execution: bool = False,
                             execution_authorization: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not organization_id or not str(order_id).strip() or not isinstance(updates, Mapping) or not updates:
            return {"success": False, "status": "blocked", "error": "order_update_identity_required", "executed": False}
        if not approved_execution or not execution_authorization:
            return {"success": False, "status": "blocked", "error": "canonical_execution_required", "executed": False}
        token = resolve_secret(self.PROVIDER, "access_token", organization_id=int(organization_id))
        response = governed_request(
            "PUT", self._target(f"orders/{str(order_id).strip()}"),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"},
            json=dict(updates), timeout=30, allow_redirects=False,
        )
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not response.ok:
            return redact({"success": False, "status": "failed", "executed": True,
                           "provider_status": response.status_code, "error": "provider_rejected_request", "provider_error": body})
        return redact({"success": True, "status": "completed", "executed": True,
                       "provider": self.PROVIDER, "provider_status": response.status_code,
                       "data": body.get("data", body)})

    @classmethod
    def build_webhook_execution_request(cls, *, organization_id: int, event: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(event.get("payload") or {})
        data = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload
        order_id = str(event.get("external_id") or data.get("id") or "").strip()
        if not organization_id or not order_id:
            raise ValueError("salla_order_identity_required")
        updates = {}
        for key in ("customer", "receiver", "ship_to", "delivery_method", "branch_id", "courier_id"):
            value = data.get(key)
            if value not in (None, "", {}, []):
                updates[key] = value
        if not updates:
            raise ValueError("salla_order_update_proposal_missing")
        return {
            "action": "salla_update_order",
            "parameters": {
                "organization_id": int(organization_id),
                "order_id": order_id,
                "updates": updates,
            },
            "reason": f"Governed Salla response to {event.get('event')} for order {order_id}.",
        }

    def execute_get_order(self, *, organization_id: int, order_id: str,
                          approved_execution: bool = False, execution_authorization: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not organization_id or not str(order_id).strip():
            return {"success": False, "status": "blocked", "error": "order_identity_required", "executed": False}
        token = resolve_secret(self.PROVIDER, "access_token", organization_id=int(organization_id))
        response = governed_request("GET", self._target(f"orders/{str(order_id).strip()}"),
                                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=30, allow_redirects=False)
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not response.ok:
            return redact({"success": False, "status": "failed", "executed": True,
                           "provider_status": response.status_code, "error": "provider_rejected_request", "provider_error": body})
        return redact({"success": True, "status": "completed", "executed": True,
                       "provider": self.PROVIDER, "provider_status": response.status_code, "data": body.get("data", body)})

    @classmethod
    def verify_webhook(cls, *, organization_id: int, headers: Mapping[str, str]) -> bool:
        if not organization_id:
            return False
        header_name = os.getenv(cls.WEBHOOK_HEADER_ENV, "Authorization").strip()
        supplied = str(headers.get(header_name, "") or "").strip()
        if not supplied:
            return False
        try:
            expected = resolve_secret(cls.PROVIDER, "webhook_secret", organization_id=int(organization_id))
        except (ValueError, RuntimeError):
            return False
        return hmac.compare_digest(supplied, expected)

    @classmethod
    def materialize_webhook_workflow(cls, *, organization_id: int, event: Mapping[str, Any],
                                      requested_by: int | None = None) -> dict[str, Any]:
        from app import db
        from app.core.automation_queue import automation_queue
        from app.models.automation import AutomationAction, AutomationExecution, AutomationWorkflow
        from app.services.automation_approval_service import automation_approval_service

        proposal = cls.build_webhook_execution_request(organization_id=int(organization_id), event=event)
        execution_key = str(event["idempotency_key"])
        existing = AutomationExecution.query.filter_by(idempotency_key=execution_key).first()
        if existing is not None:
            return {"success": True, "status": "deduplicated", "execution_id": existing.id, "idempotency_key": execution_key}

        workflow = AutomationWorkflow(
            organization_id=int(organization_id),
            name=f"Salla · {event['event']} · {event['external_id']}",
            description="Governed Salla webhook workflow.",
            trigger_type="salla_webhook", is_active=True,
        )
        db.session.add(workflow)
        db.session.flush()
        db.session.add(AutomationAction(
            workflow_id=workflow.id, position=1, action_type=proposal["action"],
            config_json=json.dumps(proposal["parameters"], ensure_ascii=False, default=str), is_active=True,
        ))
        execution = AutomationExecution(
            workflow_id=workflow.id, trigger_type="salla_webhook",
            idempotency_key=execution_key, status="waiting_approval",
            input_json=json.dumps(event, ensure_ascii=False, default=str),
        )
        db.session.add(execution)
        db.session.flush()

        queued = automation_queue.enqueue({
            "organization_id": int(organization_id), "job_key": execution_key,
            "event_id": event["external_id"], "trigger_id": event["event"],
            "workflow_id": str(workflow.id), "execution_id": str(execution.id),
            "idempotency_key": execution_key, "workflow_state": "waiting_approval",
            "payload": event, "actor_id": requested_by,
        }, commit=False)
        approval = automation_approval_service.create(
            organization_id=int(organization_id), action_type=proposal["action"],
            reason=proposal["reason"], request_data={
                "action": proposal["action"], "parameters": proposal["parameters"],
                "data": {"event": event["event"], "external_id": event["external_id"]},
            }, workflow_id=workflow.id, execution_id=execution.id, requested_by=requested_by,
        )
        if not approval.get("success"):
            db.session.rollback()
            return approval
        return {
            "success": True, "status": "approval_required",
            "workflow_id": workflow.id, "execution_id": execution.id,
            "job_id": queued.get("job_id"), "approval_id": approval["approval_id"],
            "idempotency_key": execution_key,
        }

    @classmethod
    def normalize_webhook(cls, *, organization_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        event = str(payload.get("event") or payload.get("type") or "").strip()
        data = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload
        external_id = str(
            data.get("id") or data.get("order_id") or data.get("_id") or payload.get("id") or ""
        ).strip()
        if not organization_id or not event or not external_id:
            raise ValueError("salla_webhook_identity_required")
        return {
            "provider": cls.PROVIDER, "organization_id": int(organization_id), "event": event,
            "external_id": external_id, "idempotency_key": cls.idempotency_key(
                organization_id=organization_id, event=event, external_id=external_id),
            "payload": json.loads(json.dumps(payload, ensure_ascii=False, default=str)),
            "governance": {"external_execution": False, "database_mutation": False,
                           "auto_execute": False, "queue_before_processing": True,
                           "source_trust": "provider_webhook_untrusted_until_verified"},
        }


salla_connector_service = SallaConnectorService()
