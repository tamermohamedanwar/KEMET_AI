from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services.revenue_pipeline_service import revenue_pipeline_service
from app.services.commercial_offer_service import commercial_offer_service


revenue_pipeline_bp = Blueprint("revenue_pipeline", __name__)


def _org_id():
    return getattr(current_user, "organization_id", None)


def _json_error(exc):
    return jsonify({"success": False, "status": "blocked", "error": str(exc)}), 400


@revenue_pipeline_bp.post("/command-center/api/bos/revenue-pipeline/intake")
@login_required
def intake():
    try:
        payload = request.get_json(silent=True) or {}
        result = revenue_pipeline_service.intake(
            organization_id=int(_org_id()), company_name=payload.get("company_name"),
            email=payload.get("email"), phone=payload.get("phone", ""), message=payload.get("message", ""),
            source=payload.get("source", "command_center"), offer_name=payload.get("offer_name", ""),
            quoted_amount=payload.get("quoted_amount", 0), pipeline_key=payload.get("pipeline_key", ""),
        )
        return jsonify(result), 201
    except Exception as exc:
        return _json_error(exc)


@revenue_pipeline_bp.get("/command-center/api/bos/revenue-pipeline/<pipeline_key>")
@login_required
def get_pipeline(pipeline_key):
    try:
        record = revenue_pipeline_service._record(int(_org_id()), pipeline_key)
        return jsonify(revenue_pipeline_service.snapshot(record))
    except Exception as exc:
        return _json_error(exc)


@revenue_pipeline_bp.get("/command-center/api/bos/revenue-pipeline")
@login_required
def dashboard():
    try:
        return jsonify(revenue_pipeline_service.dashboard(int(_org_id())))
    except Exception as exc:
        return _json_error(exc)


@revenue_pipeline_bp.post("/command-center/api/bos/revenue-pipeline/<pipeline_key>/advance")
@login_required
def advance(pipeline_key):
    try:
        payload = request.get_json(silent=True) or {}
        result = revenue_pipeline_service.advance(
            organization_id=int(_org_id()), pipeline_key=pipeline_key, stage=payload.get("stage")
        )
        return jsonify(result)
    except Exception as exc:
        return _json_error(exc)


@revenue_pipeline_bp.post("/command-center/api/bos/revenue-pipeline/<pipeline_key>/payment")
@login_required
def attach_payment(pipeline_key):
    try:
        payload = request.get_json(silent=True) or {}
        result = revenue_pipeline_service.attach_payment(
            organization_id=int(_org_id()), pipeline_key=pipeline_key, payment_id=int(payload.get("payment_id"))
        )
        return jsonify(result)
    except Exception as exc:
        return _json_error(exc)


@revenue_pipeline_bp.post("/command-center/api/bos/revenue-pipeline/<pipeline_key>/cost")
@login_required
def record_cost(pipeline_key):
    try:
        payload = request.get_json(silent=True) or {}
        result = revenue_pipeline_service.record_cost(
            organization_id=int(_org_id()), pipeline_key=pipeline_key, category=payload.get("category"), amount=payload.get("amount")
        )
        return jsonify(result)
    except Exception as exc:
        return _json_error(exc)


@revenue_pipeline_bp.post("/command-center/api/bos/revenue-pipeline/<pipeline_key>/delivery")
@login_required
def attach_delivery(pipeline_key):
    try:
        payload = request.get_json(silent=True) or {}
        result = revenue_pipeline_service.attach_delivery(
            organization_id=int(_org_id()), pipeline_key=pipeline_key, fulfillment_reference=payload.get("fulfillment_reference")
        )
        return jsonify(result)
    except Exception as exc:
        return _json_error(exc)



@revenue_pipeline_bp.post('/command-center/api/bos/revenue-pipeline/<pipeline_key>/qualification')
@login_required
def qualify(pipeline_key):
    try:
        payload = request.get_json(silent=True) or {}
        result = commercial_offer_service.qualify(
            organization_id=int(_org_id()), pipeline_key=pipeline_key,
            qualification=payload.get("qualification") or payload,
        )
        return jsonify(result)
    except Exception as exc:
        return _json_error(exc)


@revenue_pipeline_bp.post('/command-center/api/bos/revenue-pipeline/<pipeline_key>/offer/draft')
@login_required
def draft_offer(pipeline_key):
    try:
        payload = request.get_json(silent=True) or {}
        result = commercial_offer_service.draft_offer(
            organization_id=int(_org_id()), pipeline_key=pipeline_key,
            offer_name=payload.get("offer_name"), offer_description=payload.get("offer_description"),
            quoted_amount=payload.get("quoted_amount"), currency=payload.get("currency", "EGP"),
        )
        return jsonify(result), 201
    except Exception as exc:
        return _json_error(exc)

@revenue_pipeline_bp.post("/command-center/api/bos/revenue-pipeline/<pipeline_key>/offer/approve")
@login_required
def approve_offer(pipeline_key):
    try:
        payload = request.get_json(silent=True) or {}
        offer_id = int(payload.get("offer_id"))
        result = commercial_offer_service.approve(
            organization_id=int(_org_id()), offer_id=offer_id, approver_id=int(current_user.id)
        )
        return jsonify(result), 200 if result.get("success") else 422
    except Exception as exc:
        return _json_error(exc)


@revenue_pipeline_bp.post("/command-center/api/bos/revenue-pipeline/<pipeline_key>/close")
@login_required
def close(pipeline_key):
    try:
        result = revenue_pipeline_service.close(organization_id=int(_org_id()), pipeline_key=pipeline_key)
        return jsonify(result)
    except Exception as exc:
        return _json_error(exc)
