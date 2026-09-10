from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.integration import KemetActivationService


from app.core.context.live_business_data import LiveBusinessData
class KemetCommandCenterWiring:


    def build_command_context(
        self,
        organization_id=None,
        user_id=None,
        message="",
    ):
        """Build a read-only live context for a command request."""
        live = self.live_context(organization_id)

        return {
            "organization_id": organization_id,
            "user_id": user_id,
            "message": message,
            "live_business": live,
            "mode": "advisory",
            "approval_required": True,
            "external_execution": False,
            "database_mutation": False,
        }

    def live_context(self, organization_id=None):
        """Return a read-only live business context for the command center."""
        snapshot = LiveBusinessData().snapshot(organization_id)
        return snapshot.to_dict()


    """
    Governance-safe bridge between the existing Command Center
    and the Kemet activation layer.

    This layer does not replace existing routes, does not mutate
    the database, and does not execute external actions.
    """

    VERSION = "1.0"

    def __init__(self, activation_service: Optional[KemetActivationService] = None):
        self.activation = activation_service or KemetActivationService()

    def analyze(
        self,
        revenue_data: Optional[Dict[str, Any]] = None,
        sales_data: Optional[Dict[str, Any]] = None,
        customer_data: Optional[Dict[str, Any]] = None,
        analytics_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result = self.activation.analyze(
            revenue_data=revenue_data or {},
            sales_data=sales_data or {},
            customer_data=customer_data or {},
            analytics_data=analytics_data or {},
        )

        return {
            "ok": True,
            "engine": "kemet_command_center_wiring",
            "version": self.VERSION,
            "mode": "advisory",
            "analysis": result,
            "external_execution": False,
            "database_mutation": False,
        }

    def run(
        self,
        revenue_data: Optional[Dict[str, Any]] = None,
        sales_data: Optional[Dict[str, Any]] = None,
        customer_data: Optional[Dict[str, Any]] = None,
        analytics_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result = self.activation.run(
            revenue_data=revenue_data or {},
            sales_data=sales_data or {},
            customer_data=customer_data or {},
            analytics_data=analytics_data or {},
        )

        return {
            **result,
            "engine": "kemet_command_center_wiring",
            "version": self.VERSION,
            "mode": "advisory",
            "external_execution": False,
            "database_mutation": False,
        }

    def status(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "engine": "kemet_command_center_wiring",
            "version": self.VERSION,
            "mode": "advisory",
            "activation_layer": "active",
            "approval_required": True,
            "external_execution": False,
            "database_mutation": False,
        }
