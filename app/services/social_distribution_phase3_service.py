"""Phase 3 social distribution and measurement orchestration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any

VERSION = "1.0"
SCHEMA = "kemet.social_distribution_phase3.v1"


@dataclass(frozen=True)
class ChannelPlan:
    channel: str
    status: str
    publishable: bool
    approval_required: bool
    execution_authority: bool


class SocialDistributionPhase3Service:
    VERSION = VERSION
    SCHEMA = SCHEMA
    CHANNELS = ("youtube", "facebook", "instagram", "tiktok")

    def snapshot(self, organization_id: int) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_required")
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "channels": [self._channel(c) for c in self.CHANNELS],
            "governance": self._governance(),
        }

    def plan(self, organization_id: int, content_package: dict[str, Any],
             channels: list[str] | None = None) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_required")
        if not isinstance(content_package, dict) or not content_package:
            raise ValueError("content_package_required")
        requested = channels or list(self.CHANNELS)
        unknown = sorted(set(requested) - set(self.CHANNELS))
        if unknown:
            raise ValueError("unsupported_channel")
        digest = sha256(repr(sorted(content_package.items())).encode()).hexdigest()
        return {
            "schema": self.SCHEMA,
            "organization_id": int(organization_id),
            "content_digest": digest,
            "plans": [self._channel(c) for c in requested],
            "approval": {"required": True, "state": "PENDING"},
            "executed": False,
            "execution_authority": False,
            "external_side_effect": False,
        }

    def _channel(self, channel: str) -> dict[str, Any]:
        return asdict(ChannelPlan(channel, "READINESS_REQUIRED", False, True, False))

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"read_only": True, "human_approval_required": True,
                "canonical_runtime_only": True, "auto_publish": False,
                "credentials_exposed": False, "mcp": False}


social_distribution_phase3_service = SocialDistributionPhase3Service()

