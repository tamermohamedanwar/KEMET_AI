from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app import csrf
from app.services.salla_connector_service import salla_connector_service
from app.services.salla_whatsapp_product_service import salla_whatsapp_product_service

salla_whatsapp_product_bp = Blueprint("salla_whatsapp_product", __name__)


def _org():
    return getattr(current_user, "organization_id", None)


@salla_whatsapp_product_bp.get("/salla-whatsapp")
@login_required
def product_page():
    organization_id = _org()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    return render_template(
        "salla_whatsapp_product.html",
        organization_id=int(organization_id),
        webhook_path=salla_whatsapp_product_service.order_webhook_url(int(organization_id)),
    )


@salla_whatsapp_product_bp.post("/api/salla-whatsapp/connect")
@login_required
def connect_product():
    organization_id = _org()
    user_id = getattr(current_user, "id", None)
    if not organization_id or not user_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    allowed = {
        "salla_access_token", "salla_webhook_secret",
        "whatsapp_access_token", "whatsapp_phone_number_id",
        "whatsapp_app_secret",
    }
    credentials = {key: payload.get(key) for key in allowed}
    try:
        result = salla_whatsapp_product_service.connect_credentials(
            organization_id=int(organization_id),
            user_id=int(user_id),
            credentials=credentials,
        )
        verification = salla_whatsapp_product_service.verify_configuration(
            organization_id=int(organization_id)
        )
        return jsonify({**result, "verification": verification}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503


@salla_whatsapp_product_bp.get("/api/salla-whatsapp/status")
@login_required
def product_status():
    organization_id = _org()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    verification = salla_whatsapp_product_service.verify_configuration(
        organization_id=int(organization_id)
    )
    try:
        phone_number_id = salla_whatsapp_product_service.default_phone_number_id(
            int(organization_id)
        )
    except (RuntimeError, ValueError):
        phone_number_id = ""
    return jsonify({
        "success": True,
        "product": "salla_whatsapp",
        "ready": bool(verification.get("verified")),
        "checks": verification.get("checks", {}),
        "phone_number_id_configured": bool(phone_number_id),
        "webhook": salla_whatsapp_product_service.order_webhook_url(int(organization_id)),
        "verification_type": verification.get("verification_type"),
        "governance": {
            "webhook_verification": True,
            "human_approval_before_external_send": True,
            "idempotency": True,
            "tenant_isolation": True,
            "encrypted_credentials": True,
        },
    })


@csrf.exempt
@salla_whatsapp_product_bp.post("/salla-whatsapp/webhook/<int:organization_id>")
def salla_whatsapp_webhook(organization_id: int):
    if not salla_connector_service.verify_webhook(
        organization_id=int(organization_id), headers=request.headers
    ):
        return jsonify({"success": False, "error": "webhook_authentication_failed"}), 403
    payload = request.get_json(silent=True) or {}
    try:
        event = salla_connector_service.normalize_webhook(
            organization_id=int(organization_id), payload=payload
        )
        phone_number_id = str(
            request.headers.get("X-Kemet-WhatsApp-Phone-Number-ID")
            or request.args.get("phone_number_id")
            or salla_whatsapp_product_service.default_phone_number_id(int(organization_id))
            or ""
        ).strip()
        if not phone_number_id:
            return jsonify({"success": False, "error": "whatsapp_phone_number_id_required"}), 422
        result = salla_whatsapp_product_service.prepare_order_notification(
            organization_id=int(organization_id),
            event=event,
            phone_number_id=phone_number_id,
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
    return jsonify(result), (202 if result.get("success") else 422)
