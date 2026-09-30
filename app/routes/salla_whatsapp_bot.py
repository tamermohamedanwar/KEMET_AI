from __future__ import annotations

from typing import Any, Mapping

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app import csrf
from app.core.secret_boundary import resolve_secret
from app.services.channel_webhook_service import channel_webhook_service
from app.services.salla_connector_service import salla_connector_service
from app.services.salla_whatsapp_product_service import salla_whatsapp_product_service

salla_whatsapp_bot_bp = Blueprint("salla_whatsapp_bot", __name__)


@salla_whatsapp_bot_bp.get("/salla-whatsapp-onboarding")
@login_required
def onboarding():
    return render_template("salla_whatsapp_onboarding.html")


def _order_status(event: Mapping[str, Any]) -> str:
    payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
    data = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload
    return str(
        data.get("status") or data.get("order_status") or data.get("shipment_status") or "قيد المعالجة"
    ).strip()


@salla_whatsapp_bot_bp.post("/salla-whatsapp-bot/webhook/<int:organization_id>")
@csrf.exempt
def salla_order_webhook(organization_id: int):
    if not salla_connector_service.verify_webhook(
        organization_id=int(organization_id), headers=request.headers
    ):
        return jsonify({"success": False, "error": "webhook_authentication_failed"}), 403

    payload = request.get_json(silent=True) or {}
    try:
        event = salla_connector_service.normalize_webhook(
            organization_id=int(organization_id), payload=payload
        )
        if str(event.get("event") or "").lower() not in {
            "order.created", "order.updated", "order.status.updated"
        }:
            return jsonify({"success": True, "status": "ignored", "event": event.get("event")}), 202

        event_payload = event.get("payload") or {}
        data = event_payload.get("data") if isinstance(event_payload.get("data"), Mapping) else event_payload
        customer = data.get("customer") if isinstance(data.get("customer"), Mapping) else {}
        phone = str(
            data.get("phone") or data.get("mobile") or customer.get("phone")
            or customer.get("mobile") or ""
        ).strip()
        if not phone:
            return jsonify({"success": False, "error": "customer_phone_required"}), 422

        phone_number_id = str(
            request.headers.get("X-Kemet-WhatsApp-Phone-Number-ID")
            or resolve_secret("meta_whatsapp_cloud_api", "phone_number_id",
                              organization_id=int(organization_id))
        ).strip()
        order_id = str(event["external_id"])
        content = (
            f"تم استلام طلبك رقم {order_id}. "
            f"حالة التوصيل الحالية: {_order_status(event)}."
        )

        # External WhatsApp execution remains governed by the existing product
        # service: it creates the canonical approval/execution handoff and never
        # bypasses the Human Approval gate.
        result = salla_whatsapp_product_service.prepare_order_notification(
            organization_id=int(organization_id),
            event=event,
            phone_number_id=phone_number_id,
        )
        result["product"] = "salla_whatsapp_bot"
        result["message_preview"] = content
        return jsonify(result), 202 if result.get("success") else 422
    except (ValueError, RuntimeError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@salla_whatsapp_bot_bp.post("/salla-whatsapp-bot/whatsapp/webhook/<int:organization_id>")
@csrf.exempt
def whatsapp_customer_reply(organization_id: int):
    raw_body = request.get_data(cache=True)
    if not channel_webhook_service.verify_meta_signature(
        raw_body=raw_body,
        signature=request.headers.get("X-Hub-Signature-256", ""),
        organization_id=int(organization_id),
    ):
        return jsonify({"success": False, "error": "webhook_authentication_failed"}), 403

    payload = request.get_json(silent=True) or {}
    messages = [
        item for item in channel_webhook_service.extract_meta(payload)
        if item.get("kind") == "message"
    ]
    if not messages:
        return jsonify({"success": True, "status": "ignored"}), 202

    # Do not directly send a Telegram notification here: the current action
    # registry has no governed telegram-send action. Returning a structured
    # alert candidate keeps the external side-effect behind Kemet's approval
    # boundary instead of silently bypassing it.
    alerts = []
    for item in messages:
        alerts.append({
            "channel": "telegram",
            "status": "approval_path_unavailable",
            "reason": "telegram_send_action_not_registered_in_canonical_runtime",
            "customer_phone": str(item.get("external_user_id") or ""),
            "message": str(item.get("text") or ""),
            "external_message_id": str(item.get("external_message_id") or ""),
        })
    return jsonify({
        "success": True,
        "status": "merchant_alert_pending_governed_action",
        "alerts": alerts,
        "governance": {"auto_execute": False, "human_approval_required": True},
    }), 202
