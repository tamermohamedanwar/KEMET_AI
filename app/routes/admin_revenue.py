from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.services.revenue_command_service import (
    RevenueCommandService,
)


admin_revenue = Blueprint(
    "admin_revenue",
    __name__,
)


@admin_revenue.route(
    "/admin/revenue",
    methods=["GET"],
)
@login_required
def revenue_dashboard():
    period = (
        request.args.get(
            "period",
            "30d",
        )
        .strip()
        .lower()
    )

    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    dashboard = RevenueCommandService.get_dashboard(
        organization_id=organization_id,
        period=period,
    )

    return render_template(
        "admin/revenue_command_center.html",
        dashboard=dashboard,
    )
