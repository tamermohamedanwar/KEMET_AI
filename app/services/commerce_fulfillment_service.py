from __future__ import annotations

import hashlib
from typing import Any, Mapping

from app.services.bosta_connector_service import bosta_connector_service


class CommerceFulfillmentService:
    VERSION = "1.0"

    def build_plan(
        self,
        *,
        organization_id: int,
        business_reference: str,
        customer: Mapping[str, Any],
        shipping_address: Mapping[str, Any],
        cod: float,
        items: list[Mapping[str, Any]],
        package_type: str = "Small",
        package_description: str = "",
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        reference = str(business_reference or "").strip()
        if not reference:
            raise ValueError("business_reference_required")
        if not isinstance(customer, Mapping):
            raise ValueError("customer_required")
        if not isinstance(shipping_address, Mapping):
            raise ValueError("shipping_address_required")
        if not isinstance(items, list) or not items:
            raise ValueError("items_required")
        proposal = bosta_connector_service.plan_create_delivery(
            organization_id=int(organization_id),
            business_reference=reference,
            customer=customer,
            shipping_address=shipping_address,
            cod=cod,
            items=items,
            package_type=package_type,
            package_description=package_description,
            webhook_url=webhook_url,
        )
        order_key = hashlib.sha256(
            f"commerce:{int(organization_id)}:{reference}".encode("utf-8")
        ).hexdigest()
        return {
            "success": True,
            "status": "approval_required",
            "engine": "kemet_commerce_fulfillment",
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "order": {
                "business_reference": reference,
                "order_key": order_key,
                "source": "governed_commerce_workflow",
            },
            "fulfillment": proposal,
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
                "human_approval_required": True,
                "canonical_executor": "kemet",
            },
        }


commerce_fulfillment_service = CommerceFulfillmentService()
