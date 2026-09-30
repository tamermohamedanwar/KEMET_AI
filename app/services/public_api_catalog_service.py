from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PublicApiCandidate:
    name: str
    category: str
    auth: str
    https: bool
    cors: str
    use_case: str


class PublicApiCatalogService:
    VERSION = "1.1"
    SOURCE = "public-apis/public-apis"
    CANDIDATES = (
        PublicApiCandidate("Google Search Console", "Search", "oauth2", True, "unknown", "search_visibility"),
        PublicApiCandidate("YouTube Data API", "Video", "oauth2", True, "unknown", "channel_metadata"),
        PublicApiCandidate("YouTube Analytics API", "Video", "oauth2", True, "unknown", "views_revenue_retention"),
        PublicApiCandidate("Google Trends", "Search", "none", True, "unknown", "topic_demand"),
    )

    @classmethod
    def snapshot(cls, organization_id: int | None) -> dict[str, Any]:
        return {
            "version": cls.VERSION,
            "source": cls.SOURCE,
            "organization_id": organization_id,
            "purpose": "discovery_only",
            "candidates": [c.__dict__ for c in cls.CANDIDATES],
            "selection_policy": {
                "official_provider_preferred": True,
                "verified_source_required": True,
                "no_secret_discovery": True,
                "no_automatic_connection": True,
            },
        }

    @classmethod
    def security_note(cls) -> dict[str, bool]:
        return {
            "catalog_is_untrusted_input": True,
            "official_sources_must_win": True,
            "credentials_never_from_catalog": True,
            "execution_authority_never_from_catalog": True,
        }


public_api_catalog_service = PublicApiCatalogService()
