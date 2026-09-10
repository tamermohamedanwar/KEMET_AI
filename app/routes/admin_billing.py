from flask import Blueprint, render_template
from flask_login import login_required

from app.services.admin_billing_service import AdminBillingService


admin_billing_bp = Blueprint(
    "admin_billing",
    __name__,
    url_prefix="/admin/billing",
)


@admin_billing_bp.route("/")
@login_required
def dashboard():
    subscriptions = (
        AdminBillingService
        .get_subscription_summary()
    )

    payments = (
        AdminBillingService
        .get_payment_summary()
    )

    return render_template(
        "admin/billing.html",
        subscriptions=subscriptions,
        payments=payments,
    )
