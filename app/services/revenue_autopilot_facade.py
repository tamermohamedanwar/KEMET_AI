from app import db
from app.models.demo_lead import DemoLead
from app.services.revenue_autopilot_service import (
    RevenueAutopilotService,
)


class RevenueAutopilotFacade:

    @classmethod
    def plan_for_lead(cls, lead_id, organization_id=None):
        if organization_id is None:
            return {
                "success": False,
                "status": "blocked",
                "error": "organization_required",
            }

        lead = db.session.get(DemoLead, lead_id)

        if not lead:
            return {
                "success": False,
                "message": "Lead not found",
            }

        if lead.organization_id != organization_id:
            return {
                "success": False,
                "status": "blocked",
                "error": "lead_organization_mismatch",
            }

        return {
            "success": True,
            "data": RevenueAutopilotService.process_lead(
                lead,
                organization_id=organization_id,
                execute=False,
            ),
        }
    @classmethod
    def run_for_lead(cls, lead_id, user_id=None, organization_id=None):
        if organization_id is None:
            return {
                "success": False,
                "status": "blocked",
                "error": "organization_required",
            }

        lead = db.session.get(DemoLead, lead_id)

        if not lead:
            return {
                "success": False,
                "message": "Lead not found",
            }

        if lead.organization_id != organization_id:
            return {
                "success": False,
                "status": "blocked",
                "error": "lead_organization_mismatch",
            }

        return {
            "success": True,
            "data": RevenueAutopilotService.process_lead(
                lead,
                user_id=user_id,
                organization_id=organization_id,
                execute=True,
            ),
        }
