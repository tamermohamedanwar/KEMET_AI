from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlatformProfile:
    name: str
    capabilities: tuple[str, ...]
    direct_publish: bool
    approval_required: bool = True


class SocialDistributionContract:
    VERSION = "1.0"
    PROFILES = {
        "youtube": PlatformProfile("youtube", ("long_video", "short_video", "scheduled_publish"), True),
        "tiktok": PlatformProfile("tiktok", ("short_video", "photo", "draft_or_direct_publish"), True),
        "instagram": PlatformProfile("instagram", ("reels", "photo", "story"), True),
        "facebook": PlatformProfile("facebook", ("video", "reels", "photo"), True),
        "telegram": PlatformProfile("telegram", ("video", "photo", "document", "channel_message"), True),
        "whatsapp": PlatformProfile("whatsapp", ("video", "photo", "template_message"), True),
        "linkedin": PlatformProfile("linkedin", ("text", "image", "video", "article"), True),
        "snapchat": PlatformProfile("snapchat", ("spotlight", "story"), False),
    }

    @classmethod
    def plan(cls, platform: str, *, asset_uri: str, title: str | None = None,
             caption: str | None = None) -> dict[str, Any]:
        key = str(platform or "").strip().lower()
        profile = cls.PROFILES.get(key)
        if profile is None:
            raise ValueError("unsupported_platform")
        return {
            "contract": cls.VERSION,
            "platform": key,
            "asset_uri": asset_uri,
            "title": title,
            "caption": caption,
            "capabilities": list(profile.capabilities),
            "direct_publish": profile.direct_publish,
            "approval_required": profile.approval_required,
            "execution_authority": False,
            "governed_executor": "kemet_canonical_runtime",
            "provider_credentials": "secret_boundary_only",
            "status": "proposal_only",
        }
