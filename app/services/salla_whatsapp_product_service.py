from __future__ import annotations

import json
from typing import Any, Mapping

from app import db
from app.models.automation import AutomationAction, AutomationExecution, AutomationWorkflow
from app.services.automation_approval_service import automation_approval_service
from app.services.salla_connector_service import salla_connector_service
from app.services.whatsapp_cloud_api_service import whatsapp_cloud_api_service


class SallaWhatsAppProductService:
    VERSION = "1.1"
    ORDER_EVENTS = {"order.created", "order.updated", "order.status.updated"}

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def connect_credentials(cls, *, organization_id: int, user_id: int,
                            credentials: Mapping[str, Any]) -> dict[str, Any]:
        required = {
            "salla_access_token": ("salla_api", "access_token"),
            "salla_webhook_secret": ("salla_api", "webhook_secret"),
            "whatsapp_access_token": ("meta_whatsapp_cloud_api", "access_token"),
            "whatsapp_phone_number_id": ("meta_whatsapp_cloud_api", "phone_number_id"),
        }
        values = {key: cls._clean(credentials.get(key)) for key in required}
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise ValueError("required_credentials_missing")
        app_secret = cls._clean(credentials.get("whatsapp_app_secret"))
        from app.core.social_credential_store import social_credential_store
        salla_payload = {
            "access_token": values["salla_access_token"],
            "webhook_secret": values["salla_webhook_secret"],
        }
        whatsapp_payload = {
            "access_token": values["whatsapp_access_token"],
            "phone_number_id": values["whatsapp_phone_number_id"],
        }
        if app_secret:
            whatsapp_payload["app_secret"] = app_secret
        salla_ref = social_credential_store.put(
            int(organization_id), int(user_id), "salla_api", salla_payload
        )
        whatsapp_ref = social_credential_store.put(
            int(organization_id), int(user_id), "whatsapp_cloud_api", whatsapp_payload
        )
        return {
            "success": True,
            "status": "configured",
            "credential_refs": {"salla": salla_ref, "whatsapp": whatsapp_ref},
            "stored_encrypted": True,
        }

    @classmethod
    def verify_configuration(cls, *, organization_id: int) -> dict[str, Any]:
        from app.core.secret_boundary import resolve_secret
        checks = {}
        for provider, name, label in (
            ("salla_api", "access_token", "salla_access_token"),
            ("salla_api", "webhook_secret", "salla_webhook_secret"),
            ("meta_whatsapp_cloud_api", "access_token", "whatsapp_access_token"),
            ("meta_whatsapp_cloud_api", "phone_number_id", "whatsapp_phone_number_id"),
        ):
            try:
                resolve_secret(provider, name, organization_id=int(organization_id))
                checks[label] = True
            except (RuntimeError, ValueError):
                checks[label] = False
        return {
            "success": True,
            "verified": all(checks.values()),
            "verification_type": "encrypted_configuration",
            "checks": checks,
        }

    @staticmethod
    def default_phone_number_id(organization_id: int) -> str:
        from app.core.secret_boundary import resolve_secret
        return resolve_secret(
            "meta_whatsapp_cloud_api", "phone_number_id",
            organization_id=int(organization_id)
        )

    @classmethod
    def order_webhook_url(cls, organization_id: int) -> str:
        return f"/salla-whatsapp/webhook/{int(organization_id)}"

    @staticmethod
    def _customer_phone(data: Mapping[str, Any]) -> str:
        for key in ("phone", "mobile", "customer_phone", "receiver_phone"):
            value = data.get(key)
            if value:
                return str(value).strip()
        for parent in ("customer", "receiver"):
            item = data.get(parent)
            if isinstance(item, Mapping):
                for key in ("phone", "mobile"):
                    value = item.get(key)
                    if value:
                        return str(value).strip()
        return ""

    @classmethod
    def build_message(cls, event: Mapping[str, Any],
                      delivery_estimate: str = "2–5 أيام") -> dict[str, Any]:
        payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
        data = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload
        order_id = str(event.get("external_id") or data.get("id") or "").strip()
        phone = cls._customer_phone(data)
        if not order_id:
            raise ValueError("order_identity_required")
        if not phone:
            raise ValueError("customer_phone_required")
        content = f"تم استلام طلبك رقم {order_id}. موعد التوصيل المتوقع: {delivery_estimate}."
        return {"order_id": order_id, "recipient": phone, "content": content}

    @classmethod
    def prepare_order_notification(cls, *, organization_id: int,
                                   event: Mapping[str, Any], phone_number_id: str,
                                   requested_by: int | None = None,
                                   delivery_estimate: str = "2–5 أيام") -> dict[str, Any]:
        event_name = str(event.get("event") or "").strip().lower()
        if event_name not in cls.ORDER_EVENTS:
            return {"success": True, "status": "ignored", "event": event_name}
        message = cls.build_message(event, delivery_estimate)
        external_id = f"salla:{event.get('idempotency_key')}:{message['order_id']}"
        plan = whatsapp_cloud_api_service.plan_send_text(
            organization_id=int(organization_id),
            recipient=message["recipient"],
            content=message["content"],
            external_message_id=external_id,
            phone_number_id=phone_number_id,
        )
        execution_key = str(plan["idempotency_key"])
        existing = AutomationExecution.query.filter_by(idempotency_key=execution_key).first()
        if existing is not None:
            return {"success": True, "status": "deduplicated",
                    "execution_id": existing.id, "idempotency_key": execution_key}

        workflow = AutomationWorkflow(
            organization_id=int(organization_id),
            name=f"Salla → WhatsApp · {message['order_id']}",
            description="Focused Salla order notification workflow.",
            trigger_type="salla_order_notification",
            is_active=True,
        )
        db.session.add(workflow)
        db.session.flush()
        db.session.add(AutomationAction(
            workflow_id=workflow.id,
            position=1,
            action_type="whatsapp_send_text",
            config_json=json.dumps({
                "organization_id": int(organization_id),
                "recipient": message["recipient"],
                "content": message["content"],
                "external_message_id": external_id,
                "phone_number_id": phone_number_id,
            }, ensure_ascii=False),
            is_active=True,
        ))
        execution = AutomationExecution(
            workflow_id=workflow.id,
            trigger_type="salla_order_notification",
            idempotency_key=execution_key,
            status="waiting_approval",
            input_json=json.dumps({"event": event, "message": message},
                                  ensure_ascii=False, default=str),
        )
        db.session.add(execution)
        db.session.flush()
        from app.core.automation_queue import automation_queue
        queued = automation_queue.enqueue({
            "organization_id": int(organization_id),
            "job_key": execution_key,
            "event_id": message["order_id"],
            "trigger_id": event_name,
            "workflow_id": str(workflow.id),
            "execution_id": str(execution.id),
            "idempotency_key": execution_key,
            "workflow_state": "waiting_approval",
            "payload": {"event": event, "message": message},
            "actor_id": requested_by,
        }, commit=False)
        approval = automation_approval_service.create(
            organization_id=int(organization_id),
            action_type="whatsapp_send_text",
            reason=f"Send Salla order confirmation for {message['order_id']}.",
            request_data={"action": "whatsapp_send_text", "parameters": {
                "organization_id": int(organization_id),
                "recipient": message["recipient"],
                "content": message["content"],
                "external_message_id": external_id,
                "phone_number_id": phone_number_id,
            }, "data": {"event": event_name, "order_id": message["order_id"]}},
            workflow_id=workflow.id,
            execution_id=execution.id,
            requested_by=requested_by,
        )
        if not approval.get("success"):
            db.session.rollback()
            return approval
        return {"success": True, "status": "approval_required",
                "workflow_id": workflow.id, "execution_id": execution.id,
                "job_id": queued.get("job_id"),
                "approval_id": approval["approval_id"],
                "idempotency_key": execution_key, "message": message}


salla_whatsapp_product_service = SallaWhatsAppProductService()
