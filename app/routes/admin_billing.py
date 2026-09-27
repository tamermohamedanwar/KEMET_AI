from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.admin.decorators import admin_required

from app.services.admin_billing_service import AdminBillingService


admin_billing_bp = Blueprint(
    "admin_billing",
    __name__,
    url_prefix="/admin/billing",
)


@admin_billing_bp.route("/")
@admin_required
def dashboard():
    subscriptions = (
        AdminBillingService
        .get_subscription_summary(current_user.organization_id)
    )

    payments = (
        AdminBillingService
        .get_payment_summary(current_user.organization_id)
    )

    return render_template(
        "admin/billing.html",
        subscriptions=subscriptions,
        payments=payments,
    )
