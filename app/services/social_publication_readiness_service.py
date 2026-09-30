"""Governed publication readiness for platforms that require explicit API/audit evidence."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


class SocialPublicationReadinessService:
    VERSION = "1.0"
    PLATFORMS = {"youtube", "tiktok", "instagram", "facebook"}

    def evaluate(self, *, organization_id: int, platform: str, metadata: dict[str, Any],
                 connected: bool, publishing_authorized: bool, api_audited: bool = False,
                 human_approval: bool = False) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            return self._blocked("organization_required")
        platform = str(platform or "").strip().lower()
        if platform not in self.PLATFORMS:
            return self._blocked("unsupported_platform")
        if not isinstance(metadata, dict):
            return self._blocked("metadata_required")
        missing = [key for key in self._required_metadata(platform) if not str(metadata.get(key) or "").strip()]
        if missing:
            return self._blocked("metadata_required", missing=missing)
        if connected is not True:
            return self._blocked("publishing_connection_not_ready")
        if publishing_authorized is not True:
            return self._blocked("publishing_authority_not_verified")
        if platform in {"youtube", "tiktok"} and api_audited is not True:
            return self._blocked("platform_api_audit_required")
        if human_approval is not True:
            return self._blocked("human_approval_required")
        payload = {"organization_id": int(organization_id), "platform": platform,
                   "metadata": metadata, "connected": True,
                   "publishing_authorized": True, "api_audited": bool(api_audited),
                   "human_approval": True}
        return {"ready": True, "version": self.VERSION, "status": "READY_FOR_CANONICAL_EXECUTION",
                "evidence_digest": sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
                "canonical_runtime_only": True, "execution_authority": False,
                "credentials_exposed": False}

    @staticmethod
    def _required_metadata(platform: str) -> tuple[str, ...]:
        return {
            "youtube": ("title", "description", "audience"),
            "tiktok": ("title", "privacy_level", "is_aigc"),
            "instagram": ("caption",),
            "facebook": ("caption",),
        }[platform]

    @staticmethod
    def _blocked(error: str, **extra: Any) -> dict[str, Any]:
        return {"ready": False, "status": "BLOCKED", "error": error, **extra,
                "canonical_runtime_only": True, "execution_authority": False,
                "credentials_exposed": False}


social_publication_readiness_service = SocialPublicationReadinessService()
