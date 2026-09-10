"""Kemet SaaS commercial control plane.

Read-only entitlement decisions for product capabilities.
No payment execution, external execution, or database mutation.
"""

from app.services.entitlement_service import EntitlementService


class SaaSControlPlane:
    VERSION = "1.0"

    CAPABILITY_FEATURES = {
        "kemet.lead_scoring": "crm",
        "kemet.ai_sales_qualification": "crm",
        "kemet.sales_follow_up": "automation",
        "kemet.customer_retention": "automation",
        "kemet.churn_detection": "advanced_analytics",
        "kemet.revenue_opportunity": "advanced_analytics",
        "kemet.payment_issue": "automation",
        "kemet.account_help": "support",
        "kemet.order_tracking": "support",
        "kemet.smart_ticket_ai": "support",
        "kemet.refund_request": "automation",
        "kemet.business_insights": "bos",
    }

    def _feature(self, capability_id):
        return self.CAPABILITY_FEATURES.get(str(capability_id or "").strip())

    def check_capability(self, organization_id, capability_id):
        if not organization_id:
            return {
                "allowed": False,
                "reason": "organization_required",
                "capability_id": capability_id,
            }

        from app.services.capability_registry import capability_registry

        capability = capability_registry.get(capability_id)
        if not capability:
            return {
                "allowed": False,
                "reason": "capability_not_found",
                "capability_id": capability_id,
            }

        feature = self._feature(capability_id)
        if not feature:
            return {
                "allowed": False,
                "reason": "capability_feature_unmapped",
                "capability_id": capability_id,
            }

        result = EntitlementService.require_feature(
            organization_id, feature
        )
        result.update({
            "capability_id": capability_id,
            "feature": feature,
            "database_mutation": False,
            "external_execution": False,
        })
        return result

    def overview(self, organization_id):
        if not organization_id:
            return {"success": False, "error": "organization_required"}

        entitlement = EntitlementService.overview(organization_id)
        capabilities = []

        from app.services.capability_registry import capability_registry

        catalog = capability_registry.catalog()
        for item in catalog:
            capability_id = item.get("capability_id")
            check = self.check_capability(
                organization_id, capability_id
            )
            capabilities.append({
                "capability_id": capability_id,
                "allowed": check.get("allowed", False),
                "feature": check.get("feature"),
                "reason": check.get("reason"),
            })

        return {
            "success": True,
            "engine": "kemet_saas_control_plane",
            "version": self.VERSION,
            "organization_id": organization_id,
            "plan": entitlement.get("plan"),
            "usage": entitlement.get("usage"),
            "features": entitlement.get("features"),
            "capabilities": capabilities,
            "governance": {
                "read_only": True,
                "advisory": True,
                "external_execution": False,
                "database_mutation": False,
                "payment_execution": False,
            },
        }


saas_control_plane = SaaSControlPlane()
