from __future__ import annotations

from typing import Any, Iterable


class FinancingCatalogService:
    """Read-only catalog contract for verified financing offers; no eligibility decision."""

    VERSION = "1.0"
    REQUIRED = ("provider", "product", "amount", "term", "pricing_basis", "fees", "eligibility", "source")

    def normalize(self, offers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for raw in offers:
            item = {key: raw.get(key) for key in self.REQUIRED}
            if not item["provider"] or not item["product"] or not item["source"]:
                continue
            item["status"] = str(raw.get("status") or "unverified").strip().lower()
            item["verified"] = item["status"] == "verified"
            item["advisory_only"] = True
            item["eligibility_decision"] = None
            result.append(item)
        return result

    def preview(self, offers: Iterable[dict[str, Any]]) -> dict[str, Any]:
        items = self.normalize(offers)
        return {"success": True, "version": self.VERSION, "status": "preview", "offers": items,
                "external_execution": False, "automatic_approval": False,
                "eligibility_decision": False, "human_review_required": True}


financing_catalog_service = FinancingCatalogService()
