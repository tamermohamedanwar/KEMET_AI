from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.services.ai_usage_service import check_limit

billing_bp = Blueprint("billing", __name__)


@billing_bp.route("/billing")
@login_required
def billing():
    usage = check_limit(current_user.organization_id)

    return render_template(
        "billing.html",
        usage=usage
    )
