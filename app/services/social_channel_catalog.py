from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SocialChannelCatalogEntry:
    channel_id: str
    name: str
    category: str
    priority: str
    publishing_model: str
    measurement: bool
    status: str


class SocialChannelCatalog:
    VERSION = "1.0"
    ENTRIES = (
        SocialChannelCatalogEntry("youtube", "YouTube", "video", "core", "oauth_api", True, "active"),
        SocialChannelCatalogEntry("tiktok", "TikTok", "short_video", "core", "oauth_api", True, "active"),
        SocialChannelCatalogEntry("instagram", "Instagram", "social_video", "core", "meta_oauth_api", True, "active"),
        SocialChannelCatalogEntry("facebook", "Facebook", "social", "core", "page_oauth_api", True, "active"),
        SocialChannelCatalogEntry("snapchat", "Snapchat", "short_video", "core", "public_profile_api", True, "catalogued"),
        SocialChannelCatalogEntry("telegram", "Telegram", "messaging", "core", "bot_api", False, "active"),
        SocialChannelCatalogEntry("whatsapp", "WhatsApp", "messaging", "core", "cloud_api", True, "active"),
        SocialChannelCatalogEntry("pinterest", "Pinterest", "visual_discovery", "important", "oauth_api", True, "catalogued"),
        SocialChannelCatalogEntry("linkedin", "LinkedIn", "professional", "important", "oauth_api", True, "catalogued"),
        SocialChannelCatalogEntry("x", "X", "social", "important", "oauth_api", True, "catalogued"),
        SocialChannelCatalogEntry("threads", "Threads", "social", "important", "meta_oauth_api", True, "catalogued"),
    )

    def snapshot(self, organization_id: int) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "channels": [entry.__dict__.copy() for entry in self.ENTRIES],
            "policy": {
                "catalogued_does_not_mean_connected": True,
                "publishing_requires_verified_provider_authority": True,
                "canonical_runtime_only": True,
                "human_approval_required": True,
            },
        }


social_channel_catalog = SocialChannelCatalog()
