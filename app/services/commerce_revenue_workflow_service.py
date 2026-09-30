from typing import Any, Mapping

from app.services.ecommerce_creative_service import ecommerce_creative_service
from app.services.governed_followup_service import governed_followup_service


class CommerceRevenueWorkflowService:
    VERSION = "1.0"

    def build_plan(self, *, organization_id: int, product: Mapping[str, Any],
                   qualification: Mapping[str, Any], lead_id: Any = None,
                   customer_id: Any = None, channel: str = "web",
                   audience: str = "", style: str = "", language: str = "ar") -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        creative = ecommerce_creative_service.build_brief(
            dict(product or {}), objective="sales", audience=audience, channel=channel,
            output_type="product_showcase", language=language, style=style,
        )
        follow_up = governed_followup_service.build_plan(
            organization_id=int(organization_id), qualification=dict(qualification or {}),
            channel=channel, customer_id=customer_id, lead_id=lead_id,
        )
        return {
            "success": True, "status": "approval_required" if follow_up["status"] == "approval_required" else follow_up["status"],
            "engine": "kemet_commerce_revenue_workflow", "version": self.VERSION,
            "organization_id": int(organization_id),
            "stages": [
                "product", "creative_brief", "lead_capture", "qualification",
                "follow_up_proposal", "human_approval", "governed_execution",
                "recorded_revenue", "roi", "learning",
            ],
            "creative": creative,
            "qualification": dict(qualification or {}),
            "follow_up": follow_up,
            "commercial": {
                "revenue": "not_available", "roi": "not_proven", "causal_claim": False,
            },
            "governance": {
                "read_only": True, "advisory": True, "database_mutation": False,
                "external_execution": False, "auto_execute": False,
                "human_approval_required": True,
            },
        }


commerce_revenue_workflow_service = CommerceRevenueWorkflowService()
