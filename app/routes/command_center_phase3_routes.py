from flask import jsonify, request
from flask_login import login_required, current_user

from app.routes.command_center import command_center_bp


def _phase3_org():
    value = getattr(current_user, "organization_id", None)
    if not value:
        return None
    return int(value)


@command_center_bp.get("/api/bos/social-distribution-phase3")
@login_required
def bos_social_distribution_phase3():
    org = _phase3_org()
    if not org:
        return jsonify({"success": False, "error": "organization_required"}), 400
    from app.services.social_distribution_phase3_service import social_distribution_phase3_service
    return jsonify({
        "success": True,
        "social_distribution": social_distribution_phase3_service.snapshot(org),
    })


@command_center_bp.post("/api/bos/social-distribution-phase3/plan")
@login_required
def bos_social_distribution_phase3_plan():
    org = _phase3_org()
    if not org:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    from app.services.social_distribution_phase3_service import social_distribution_phase3_service
    try:
        result = social_distribution_phase3_service.plan(
            org,
            payload.get("content_package"),
            payload.get("channels"),
        )
        return jsonify({"success": True, "distribution_plan": result}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400


@command_center_bp.post("/api/bos/social-measurement-phase3/normalize")
@login_required
def bos_social_measurement_phase3_normalize():
    org = _phase3_org()
    if not org:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    from app.services.social_measurement_phase3_service import social_measurement_phase3_service
    try:
        result = social_measurement_phase3_service.normalize(
            org,
            str(payload.get("channel") or ""),
            payload.get("metrics"),
        )
        return jsonify({"success": True, "measurement": result}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
