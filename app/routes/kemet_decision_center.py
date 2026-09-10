from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.core.context.live_business_data import LiveBusinessData
from app.core.decision import DecisionEngine
from app.core.orchestration.command_center_wiring import KemetCommandCenterWiring

kemet_decision_center_bp = Blueprint("kemet_decision_center", __name__)

@kemet_decision_center_bp.get("/admin/automation/decision-center")
@login_required
def decision_center():
    organization_id = getattr(current_user, "organization_id", None)
    user_id = getattr(current_user, "id", None)

    if not organization_id:
        return "Organization required", 400

    live = LiveBusinessData().snapshot(organization_id=organization_id)
    wiring = KemetCommandCenterWiring()
    live_context = wiring.live_context(organization_id=organization_id)

    decision_result = DecisionEngine().decide(
        command="Review my business",
        live_context=live_context,
    )

    return render_template(
        "admin/kemet_decision_center.html",
        organization_id=organization_id,
        user_id=user_id,
        metrics=live.to_dict(),
        decision=decision_result["decision"],
        governance={
            "mode": "advisory",
            "approval_required": True,
            "external_execution": False,
            "database_mutation": False,
        },
    )
