from flask import Blueprint, jsonify
from flask_login import login_required

from app.industries.registry import industry_registry


industry_api_bp = Blueprint(
    "industry_api",
    __name__,
    url_prefix="/api/industries",
)


@industry_api_bp.get("")
@login_required
def list_industries():
    return jsonify({
        "success": True,
        "count": len(industry_registry.list()),
        "industries": industry_registry.list(),
    })


@industry_api_bp.get("/<industry_id>")
@login_required
def get_industry(industry_id):
    industry = industry_registry.get(industry_id)

    if industry is None:
        return jsonify({
            "success": False,
            "error": "industry_not_found",
        }), 404

    return jsonify({
        "success": True,
        "industry": industry,
    })
