from flask import jsonify, request
from flask_login import current_user, login_required

from app.services.workforce_outcome_learning import workforce_outcome_learning


def register_workforce_outcome_learning_routes(bp):
    @bp.get("/outcome-learning/recommend")
    @login_required
    def outcome_learning_recommend():
        organization_id = getattr(current_user, "organization_id", None)
        payload = request.args
        result = workforce_outcome_learning.recommend(
            organization_id,
            objective=payload.get("objective", ""),
            action=payload.get("action"),
            capability=payload.get("capability"),
            role=payload.get("role"),
        )
        return jsonify(result), 200 if result.get("success") else 422

    @bp.get("/outcome-learning/snapshot")
    @login_required
    def outcome_learning_snapshot():
        organization_id = getattr(current_user, "organization_id", None)
        result = workforce_outcome_learning.learning_snapshot(
            organization_id, action=request.args.get("action"), period=request.args.get("period", "30d")
        )
        return jsonify(result), 200 if result.get("success") else 422

    return bp
