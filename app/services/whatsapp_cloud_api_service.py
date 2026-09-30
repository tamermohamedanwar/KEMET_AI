from __future__ import annotations

import hashlib
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


class WhatsAppCloudAPIService:
    VERSION = "1.0"
    PROVIDER = "meta_whatsapp_cloud_api"
    GRAPH_HOST = "graph.facebook.com"

    def contract(self, *, organization_id: int) -> ConnectorContract:
        return ConnectorContract(
            connector_id="whatsapp_cloud_api",
            version=self.VERSION,
            organization_id=int(organization_id),
            operations=("send_text", "send_media", "send_template"),
            data_scopes=("whatsapp_message", "delivery_status"),
            risk_tier="high",
            approval_level="human",
            idempotency="required",
            timeout_seconds=30,
            max_retries=0,
            reversible=False,
            evidence_required=True,
            attestation_required=False,
        )

    def _endpoint(self, phone_number_id: str, *, resolve_dns: bool = True) -> str:
        version = os.getenv("KEMET_META_GRAPH_VERSION", "v23.0").strip()
        endpoint = f"https://{self.GRAPH_HOST}/{version}/{phone_number_id}/messages"
        host = urlparse(endpoint).hostname
        return validate_public_http_target(endpoint, allow_hosts={host or self.GRAPH_HOST}, resolve_dns=resolve_dns)

    @staticmethod
    def _message_key(*, organization_id: int, external_message_id: str, content: str) -> str:
        payload = {"organization_id": int(organization_id), "external_message_id": str(external_message_id), "content": str(content)}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def plan_send_text(
        self,
        *,
        organization_id: int,
        recipient: str,
        content: str,
        external_message_id: str,
        phone_number_id: str | None = None,
    ) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        recipient = str(recipient or "").strip()
        content = str(content or "").strip()
        external_message_id = str(external_message_id or "").strip()
        if not recipient:
            raise ValueError("recipient_required")
        if not content:
            raise ValueError("message_content_required")
        if not external_message_id:
            raise ValueError("external_message_id_required")
        contract = self.contract(organization_id=int(organization_id))
        validation = contract.validate()
        if not validation["valid"]:
            raise ValueError("connector_contract_invalid")
        payload = {"messaging_product": "whatsapp", "to": recipient, "type": "text", "text": {"body": content}}
        result = {
            "success": True,
            "provider": self.PROVIDER,
            "connector": contract.as_dict(),
            "operation": "send_text",
            "delivery": "approval_required",
            "endpoint": self._endpoint(phone_number_id, resolve_dns=False) if phone_number_id else None,
            "payload": payload,
            "idempotency_key": self._message_key(
                organization_id=int(organization_id),
                external_message_id=external_message_id,
                content=content,
            ),
            "secret_references": {
                "access_token": secret_reference(self.PROVIDER, f"org:{organization_id}:access_token"),
                "app_secret": secret_reference(self.PROVIDER, f"org:{organization_id}:app_secret"),
            },
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
                "human_approval_required": True,
                "canonical_executor": "kemet",
            },
        }
        return redact(result)

    def plan_send_template(
        self,
        *,
        organization_id: int,
        recipient: str,
        template_name: str,
        language_code: str,
        external_message_id: str,
        phone_number_id: str | None = None,
        parameters: list[str] | None = None,
    ) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        recipient = str(recipient or "").strip()
        template_name = str(template_name or "").strip()
        language_code = str(language_code or "").strip()
        external_message_id = str(external_message_id or "").strip()
        if not recipient:
            raise ValueError("recipient_required")
        if not template_name:
            raise ValueError("template_name_required")
        if not language_code:
            raise ValueError("language_code_required")
        if not external_message_id:
            raise ValueError("external_message_id_required")
        contract = self.contract(organization_id=int(organization_id))
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        values = [str(value) for value in (parameters or [])]
        if values:
            payload["template"]["components"] = [{"type": "body", "parameters": [{"type": "text", "text": value} for value in values]}]
        result = {
            "success": True,
            "provider": self.PROVIDER,
            "connector": contract.as_dict(),
            "operation": "send_template",
            "delivery": "approval_required",
            "endpoint": self._endpoint(phone_number_id, resolve_dns=False) if phone_number_id else None,
            "payload": payload,
            "idempotency_key": self._message_key(
                organization_id=int(organization_id),
                external_message_id=external_message_id,
                content=json.dumps(payload, sort_keys=True),
            ),
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
                "human_approval_required": True,
                "canonical_executor": "kemet",
            },
        }
        return redact(result)

    def _registered(self, organization_id: int, operation: str) -> bool:
        result = connector_registry.register(self.contract(organization_id=organization_id))
        return bool(result.get("registered")) and connector_registry.allows(
            "whatsapp_cloud_api", operation, organization_id
        )

    def _execute_payload(
        self, *, organization_id: int, operation: str, phone_number_id: str,
        payload: dict[str, Any], idempotency_key: str,
    ) -> dict[str, Any]:
        if not self._registered(organization_id, operation):
            return {"success": False, "status": "blocked", "error": "connector_not_allowed", "executed": False}
        endpoint = self._endpoint(phone_number_id)
        try:
            token = resolve_secret(self.PROVIDER, "access_token", organization_id=organization_id)
            response = governed_request("POST", 
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=self.contract(organization_id=organization_id).timeout_seconds,
            )
            body = response.json() if response.content else {}
        except RuntimeError as exc:
            return {"success": False, "status": "blocked", "error": str(exc), "executed": False}
        except requests.RequestException as exc:
            return {"success": False, "status": "failed", "error": "provider_request_failed", "executed": True, "details": str(exc)}
        except ValueError:
            body = {}
        if not response.ok:
            return {"success": False, "status": "failed", "error": "provider_rejected_request", "provider_status": response.status_code, "provider_error": redact(body), "executed": True}
        messages = body.get("messages") if isinstance(body, dict) else None
        provider_message_id = messages[0].get("id") if messages and isinstance(messages[0], dict) else None
        return redact({
            "success": True, "status": "completed", "executed": True,
            "provider": self.PROVIDER, "operation": operation,
            "provider_status": response.status_code, "provider_message_id": provider_message_id,
            "idempotency_key": idempotency_key,
            "evidence": {"endpoint_host": self.GRAPH_HOST, "provider_message_id": provider_message_id},
        })

    def execute_send_text(self, *, organization_id: int, recipient: str, content: str,
                          external_message_id: str, phone_number_id: str,
                          approved_execution: bool = False,
                          execution_authorization: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not approved_execution or not isinstance(execution_authorization, Mapping):
            return {"success": False, "status": "blocked", "error": "canonical_execution_required", "executed": False}
        plan = self.plan_send_text(organization_id=organization_id, recipient=recipient,
                                   content=content, external_message_id=external_message_id,
                                   phone_number_id=phone_number_id)
        return self._execute_payload(organization_id=organization_id, operation="send_text",
                                     phone_number_id=phone_number_id, payload=plan["payload"],
                                     idempotency_key=plan["idempotency_key"])

    def execute_send_template(self, *, organization_id: int, recipient: str, template_name: str,
                              language_code: str, external_message_id: str, phone_number_id: str,
                              parameters: list[str] | None = None,
                              approved_execution: bool = False,
                              execution_authorization: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not approved_execution or not isinstance(execution_authorization, Mapping):
            return {"success": False, "status": "blocked", "error": "canonical_execution_required", "executed": False}
        plan = self.plan_send_template(organization_id=organization_id, recipient=recipient,
                                       template_name=template_name, language_code=language_code,
                                       external_message_id=external_message_id, phone_number_id=phone_number_id,
                                       parameters=parameters)
        return self._execute_payload(organization_id=organization_id, operation="send_template",
                                     phone_number_id=phone_number_id, payload=plan["payload"],
                                     idempotency_key=plan["idempotency_key"])

    def delivery_event(self, *, organization_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        status = str(payload.get("status") or "").strip().lower()
        if status not in {"sent", "delivered", "read", "failed"}:
            raise ValueError("invalid_delivery_status")
        message_id = str(payload.get("message_id") or "").strip()
        if not message_id:
            raise ValueError("message_id_required")
        return {
            "success": True,
            "provider": self.PROVIDER,
            "organization_id": int(organization_id),
            "message_id": message_id,
            "status": status,
            "source": "whatsapp.cloud.webhook",
            "durable_ingress_required": True,
            "governance": {"external_execution": False, "database_mutation": True, "auto_execute": False},
        }


whatsapp_cloud_api_service = WhatsAppCloudAPIService()
