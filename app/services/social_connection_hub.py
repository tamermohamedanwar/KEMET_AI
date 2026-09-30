from __future__ import annotations

from typing import Any

from app.services.social_channel_readiness_service import social_channel_readiness_service
from app.services.social_connection_service import social_connection_service


class SocialConnectionHub:
    VERSION = "1.0"

    def snapshot(self, organization_id: int, user_id: int | None = None) -> dict[str, Any]:
        readiness = social_channel_readiness_service.snapshot(int(organization_id))
        from app.core.federation.connection_lifecycle import ConnectionLifecycleService
        connections = {row.provider_id: row for row in ConnectionLifecycleService.list_for_user(int(organization_id), int(user_id))} if user_id else {}
        rows = []
        for channel in readiness.get("channels", []):
            connection = connections.get(f"social:{channel.get('channel_id')}")
            rows.append({
                "channel_id": channel.get("channel_id"),
                "name": channel.get("name"),
                "provider": channel.get("provider"),
                "configuration": channel.get("configuration"),
                "connection": connection.status if connection else channel.get("connection", "not_connected"),
                "publish_state": channel.get("publish_state", "approval_required"),
                "measurement_ready": bool(channel.get("measurement_ready")),
                "publishing_authority": channel.get("publishing_authority"),
                "next_step": self._next_step(channel),
            })
        return {
            "success": True,
            "version": self.VERSION,
            "mode": "unified_onboarding",
            "channels": rows,
            "connect_all": {
                "available": True,
                "means": "one_dashboard_multiple_official_authorizations",
                "single_token": False,
                "canonical_runtime": "kemet_canonical_runtime",
            },
            "governance": {
                "read_only": True,
                "no_credentials_exposed": True,
                "login_oauth_is_not_publishing_authority": True,
                "publishing_requires_approval": True,
            },
        }

    def authorize(self, organization_id: int, user_id: int, channel: str) -> dict[str, Any]:
        channel = str(channel or "").strip().lower()
        if channel not in {"youtube", "tiktok", "instagram", "facebook"}:
            return {"success": False, "channel": channel,
                    "error": "channel_uses_existing_or_non_oauth_connection_path"}
        return social_connection_service.authorize(int(organization_id), int(user_id), channel)

    @staticmethod
    def _next_step(channel: dict[str, Any]) -> str:
        if channel.get("connection") == "verified":
            return "publish_ready_after_approval"
        if channel.get("configuration") == "configured":
            return "authorize_and_verify"
        return "configure_official_credentials"


social_connection_hub = SocialConnectionHub()
