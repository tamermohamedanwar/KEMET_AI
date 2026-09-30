from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VisibilitySurface:
    surface_id: str
    name: str
    kind: str
    status: str


class KemetVisibilityIntelligenceService:
    VERSION = "1.0"
    SURFACES = (
        VisibilitySurface("google_search", "Google Search", "search", "not_connected"),
        VisibilitySurface("chatgpt", "ChatGPT", "ai_answer", "not_connected"),
        VisibilitySurface("gemini", "Gemini", "ai_answer", "not_connected"),
    )

    @classmethod
    def snapshot(cls, organization_id: int | None, market: str = "global") -> dict[str, Any]:
        surfaces = [
            {
                "surface_id": s.surface_id,
                "name": s.name,
                "kind": s.kind,
                "status": s.status,
                "queries_monitored": None,
                "mentions": None,
                "visibility_rate": None,
                "position_or_presence": None,
                "competitor_presence": None,
                "source_verified": False,
            }
            for s in cls.SURFACES
        ]
        return {
            "version": cls.VERSION,
            "organization_id": organization_id,
            "market": market,
            "brand": "Kemet",
            "status": "measurement_ready",
            "surfaces": surfaces,
            "totals": {
                "queries_monitored": None,
                "brand_mentions": None,
                "visibility_rate": None,
                "qualified_discovery": None,
                "visibility_gap_count": None,
            },
            "gaps": [],
            "opportunities": [],
            "recommended_actions": [],
            "loop": [
                "content", "distribution", "visibility", "audience",
                "qualified_views", "revenue", "learning",
            ],
            "governance": {
                "read_only": True,
                "tenant_scoped": True,
                "no_auto_publish": True,
                "no_external_execution": True,
                "no_fabricated_metrics": True,
            },
        }

    @classmethod
    def public_api_discovery(cls, organization_id: int | None) -> dict[str, Any]:
        from app.services.public_api_catalog_service import public_api_catalog_service
        return public_api_catalog_service.snapshot(organization_id)


kemet_visibility_intelligence_service = KemetVisibilityIntelligenceService()
