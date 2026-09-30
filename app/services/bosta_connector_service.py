from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.integration.connector_contract import ConnectorContract
from app.core.integration.connector_registry import connector_registry
from app.core.secret_boundary import redact, resolve_secret, secret_reference


class BostaConnectorService:
    VERSION = "1.0"
    PROVIDER = "bosta_api"
    BASE_URL = "https://app.bosta.co/api/v2"
    OPERATIONS = ("create_delivery",)
    STATES = {10: "pickup_requested", 20: "route_assigned", 21: "picked_up", 24: "received_at_warehouse", 30: "in_transit", 41: "out_for_delivery", 45: "delivered", 46: "returned", 47: "exception", 48: "terminated", 49: "canceled", 100: "lost", 101: "damaged", 60: "returned_to_stock"}

    def contract(self, organization_id: int) -> ConnectorContract:
        return ConnectorContract(
            connector_id="bosta_api", version=self.VERSION, organization_id=int(organization_id),
            operations=self.OPERATIONS, data_scopes=("order", "shipment", "tracking_status"),
            risk_tier="high", approval_level="human", idempotency="required",
            timeout_seconds=30, max_retries=0, reversible=False, evidence_required=True,
        )

    @staticmethod
    def _validate_target() -> str:
        target = f"{BostaConnectorService.BASE_URL}/deliveries?apiVersion=1"
        validate_public_http_target(target)
        return target

    @staticmethod
    def _idempotency_key(organization_id: int, business_reference: str) -> str:
        raw = f"bosta:{int(organization_id)}:{str(business_reference).strip()}".encode()
        return hashlib.sha256(raw).hexdigest()

    def plan_create_delivery(self, *, organization_id: int, business_reference: str,
                             customer: Mapping[str, Any], shipping_address: Mapping[str, Any],
                             cod: float, items: list[Mapping[str, Any]],
                             package_type: str = "Small", package_description: str = "",
                             webhook_url: str | None = None) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        if not str(business_reference or "").strip():
            raise ValueError("business_reference_required")
        if not isinstance(customer, Mapping) or not customer.get("firstName") or not customer.get("mobile"):
            raise ValueError("customer_required")
        if not isinstance(shipping_address, Mapping) or not shipping_address.get("city") and not shipping_address.get("cityId"):
            raise ValueError("shipping_address_city_required")
        if float(cod) < 0 or float(cod) > 30000:
            raise ValueError("cod_out_of_range")
        if not isinstance(items, list) or not items:
            raise ValueError("items_required")
        contract = self.contract(int(organization_id))
        registered = connector_registry.register(contract)
        if not registered.get("registered"):
            raise ValueError("connector_not_registered")
        payload: dict[str, Any] = {
            "type": 10, "businessReference": str(business_reference), "cod": float(cod),
            "customer": dict(customer), "dropOffAddress": dict(shipping_address),
            "specs": {"packageDetails": {"description": package_description, "itemsCount": len(items)}, "packageType": package_type},
            "items": [dict(item) for item in items],
        }
        if webhook_url:
            parsed = urlparse(webhook_url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("webhook_url_invalid")
            payload["webhookUrl"] = webhook_url
        return redact({
            "success": True, "status": "proposal", "provider": self.PROVIDER,
            "operation": "create_delivery", "organization_id": int(organization_id),
            "payload": payload, "endpoint": self._validate_target(),
            "idempotency_key": self._idempotency_key(organization_id, business_reference),
            "secret_reference": secret_reference(self.PROVIDER, "api_key"),
            "governance": {"read_only": False, "external_execution": False, "database_mutation": False,
                           "auto_execute": False, "human_approval_required": True, "canonical_executor": "kemet"},
        })

    def execute_create_delivery(self, *, organization_id: int, approved_execution: bool = False,
                                execution_authorization: Mapping[str, Any] | None = None,
                                **kwargs: Any) -> dict[str, Any]:
        if not approved_execution or not isinstance(execution_authorization, Mapping):
            return {"success": False, "status": "blocked", "error": "canonical_execution_required", "executed": False}
        plan = self.plan_create_delivery(organization_id=organization_id, **kwargs)
        if not connector_registry.allows(self.PROVIDER, "create_delivery", int(organization_id)):
            return {"success": False, "status": "blocked", "error": "connector_operation_not_allowed", "executed": False}
        api_key = resolve_secret(self.PROVIDER, "api_key", organization_id=int(organization_id))
        response = governed_request("POST", plan["endpoint"], headers={"Authorization": api_key, "Content-Type": "application/json"},
                                 data=json.dumps(plan["payload"]), timeout=30, allow_redirects=False)
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not response.ok:
            return redact({"success": False, "status": "failed", "executed": True, "provider_status": response.status_code,
                           "error": "provider_rejected_request", "provider_error": body})
        data = body.get("data") if isinstance(body, dict) else {}
        order = data.get("order") if isinstance(data, dict) else {}
        return redact({"success": True, "status": "completed", "executed": True, "provider": self.PROVIDER,
                       "provider_status": response.status_code, "order_id": order.get("_id") or order.get("id") or data.get("_id"),
                       "tracking_number": order.get("trackingNumber") or data.get("trackingNumber"),
                       "business_reference": kwargs.get("business_reference"),
                       "evidence": {"provider": self.PROVIDER, "operation": "create_delivery"}})

    @staticmethod
    def verify_webhook(*, authorization: str) -> bool:
        expected = os.getenv("KEMET_BOSTA_WEBHOOK_SECRET", "").strip()
        supplied = str(authorization or "").strip()
        return bool(expected and supplied) and hmac.compare_digest(supplied, expected)

    def correlate_execution(self, *, organization_id: int, order_id: str = "", tracking_number: str = "", business_reference: str = "") -> dict[str, Any] | None:
        from app.models.execution_evidence import ExecutionEvidence

        tokens = [str(order_id or "").strip(), str(tracking_number or "").strip(), str(business_reference or "").strip()]
        tokens = [token for token in tokens if token]
        if not organization_id or not tokens:
            return None
        query = ExecutionEvidence.query.filter(ExecutionEvidence.organization_id == int(organization_id))
        for token in tokens:
            row = query.filter(ExecutionEvidence.receipt_json.like(f"%{token}%")).order_by(ExecutionEvidence.id.desc()).first()
            if row is not None:
                return {"execution_key": row.execution_key, "job_id": row.job_id, "evidence_key": row.evidence_key}
        return None

    def record_tracking_evidence(self, *, organization_id: int, event: Mapping[str, Any]) -> dict[str, Any]:
        from app.core.execution_evidence import execution_evidence

        correlation = self.correlate_execution(
            organization_id=organization_id,
            order_id=str(event.get("order_id") or ""),
            tracking_number=str(event.get("tracking_number") or ""),
            business_reference=str(event.get("business_reference") or ""),
        )
        result = {"execution_key": correlation.get("execution_key") if correlation else None,
                  "job_id": correlation.get("job_id") if correlation else None, "correlation": correlation}
        if correlation:
            evidence_key = f"bosta:{int(organization_id)}:fulfillment:{event.get('order_id')}:{event.get('state')}:{event.get('timestamp')}"
            execution_evidence.record(
                organization_id=int(organization_id), execution_key=correlation["execution_key"],
                job_id=correlation.get("job_id"), stage="fulfillment.tracking",
                status=str(event.get("state_name") or "unknown"), evidence_key=evidence_key,
                receipt={"provider": self.PROVIDER, "order_id": event.get("order_id"),
                         "tracking_number": event.get("tracking_number"),
                         "business_reference": event.get("business_reference"),
                         "state": event.get("state"), "state_name": event.get("state_name"),
                         "is_confirmed_delivery": event.get("is_confirmed_delivery"),
                         "exception_reason": event.get("exception_reason"),
                         "exception_code": event.get("exception_code"),
                         "number_of_attempts": event.get("number_of_attempts")},
            )
        return result

    def normalize_tracking_event(self, *, organization_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        order_id = str(payload.get("_id") or "").strip()
        if not order_id:
            raise ValueError("bosta_order_id_required")
        state = int(payload.get("state")) if payload.get("state") is not None else None
        return {
            "provider": self.PROVIDER, "organization_id": int(organization_id), "order_id": order_id,
            "tracking_number": str(payload.get("trackingNumber") or ""), "state": state,
            "state_name": self.STATES.get(state, "unknown"), "type": payload.get("type"),
            "business_reference": payload.get("businessReference"), "timestamp": payload.get("timeStamp"),
            "is_confirmed_delivery": payload.get("isConfirmedDelivery"), "cod": payload.get("cod"),
            "exception_reason": payload.get("exceptionReason"), "exception_code": payload.get("exceptionCode"),
            "number_of_attempts": payload.get("numberOfAttempts"),
            "governance": {"external_execution": False, "database_mutation": True, "auto_execute": False},
        }


bosta_connector_service = BostaConnectorService()
