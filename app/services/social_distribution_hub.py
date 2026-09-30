from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from app.services.social_distribution_contract import SocialDistributionContract
from app.services.social_channel_readiness_service import social_channel_readiness_service


@dataclass(frozen=True)
class DistributionTarget:
    platform: str
    publish_mode: str
    measurement: bool
    connection_purpose: str


class SocialDistributionHub:
    VERSION = "1.0"
    ACTIONS = {
        "youtube": "youtube_publish",
        "tiktok": "tiktok_publish",
        "instagram": "instagram_publish",
        "facebook": "facebook_publish",
        "telegram": "telegram_publish",
        "whatsapp": "whatsapp_publish",
        "linkedin": "linkedin_publish",
    }
    TARGETS = {
        "youtube": DistributionTarget("youtube", "direct_publish", True, "content_publishing"),
        "tiktok": DistributionTarget("tiktok", "direct_or_draft", True, "content_publishing"),
        "instagram": DistributionTarget("instagram", "direct_publish", True, "content_publishing"),
        "facebook": DistributionTarget("facebook", "direct_publish", True, "content_publishing"),
        "telegram": DistributionTarget("telegram", "direct_publish", False, "content_publishing"),
        "whatsapp": DistributionTarget("whatsapp", "direct_publish", True, "content_publishing"),
        "linkedin": DistributionTarget("linkedin", "proposal_only", True, "content_publishing"),
    }

    def plan(self, organization_id: int, *, asset_uri: str, title: str | None = None,
             caption: str | None = None, platforms: list[str] | None = None) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_required")
        if not str(asset_uri or "").strip():
            raise ValueError("asset_uri_required")
        selected = [str(item).strip().lower() for item in (platforms or self.TARGETS)]
        unknown = [item for item in selected if item not in self.TARGETS]
        if unknown:
            raise ValueError("unsupported_platform")
        readiness = social_channel_readiness_service.snapshot(int(organization_id))
        by_id = {row["id"]: row for row in readiness["channels"]}
        targets = []
        for platform in selected:
            profile = SocialDistributionContract.PROFILES[platform]
            state = by_id.get(platform, {})
            target = self.TARGETS[platform]
            targets.append({
                "platform": platform,
                "action": self.ACTIONS[platform],
                "capabilities": list(profile.capabilities),
                "publish_mode": target.publish_mode,
                "connection_purpose": target.connection_purpose,
                "connection": state.get("connection", "not_connected"),
                "configured": bool(state.get("configured")),
                "measurement_ready": target.measurement,
                "requires_approval": True,
                "execution_authority": False,
                "credentials_exposed": False,
            })
        package = {
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "asset_uri": str(asset_uri),
            "title": title,
            "caption": caption,
            "targets": targets,
            "approval": {"required": True, "scope": "distribution_package"},
            "execution": {"runtime": "kemet_canonical_runtime", "automatic": False},
            "idempotency": "content_distribution_v1",
            "status": "proposal_only",
        }
        canonical = json.dumps(package, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        package["package_digest"] = sha256(canonical.encode("utf-8")).hexdigest()
        return package

    def snapshot(self, organization_id: int) -> dict[str, Any]:
        readiness = social_channel_readiness_service.snapshot(int(organization_id))
        return {
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "channels": readiness["channels"],
            "execution": {"canonical_runtime_only": True, "approval_required": True},
            "connection_rule": "content_publishing_oauth_is_distinct_from_user_login_oauth",
            "credentials_exposed": False,
        }


social_distribution_hub = SocialDistributionHub()
