from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.social_channel_catalog import social_channel_catalog


@dataclass(frozen=True)
class ChannelDefinition:
    channel_id: str
    name: str
    provider: str
    env_keys: tuple[str, ...]
    capabilities: tuple[str, ...]
    measurement: bool
    publishing_authority: str


class SocialChannelReadinessService:
    VERSION = "1.2"
    CHANNELS = (
        ChannelDefinition("youtube", "YouTube", "google", ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "YOUTUBE_PUBLISH_SCOPES"), ("publish", "analytics"), True, "youtube_upload_oauth"),
        ChannelDefinition("tiktok", "TikTok", "tiktok", ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REDIRECT_URI"), ("publish", "analytics"), True, "video.publish_or_video.upload"),
        ChannelDefinition("instagram", "Instagram", "meta", ("INSTAGRAM_CLIENT_ID", "INSTAGRAM_CLIENT_SECRET", "INSTAGRAM_REDIRECT_URI"), ("publish", "analytics"), True, "instagram_publishing_oauth"),
        ChannelDefinition("facebook", "Facebook", "meta", ("FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_SECRET", "FACEBOOK_REDIRECT_URI"), ("publish", "analytics"), True, "facebook_page_publishing_oauth"),
        ChannelDefinition("snapchat", "Snapchat", "snap", ("SNAPCHAT_CLIENT_ID", "SNAPCHAT_CLIENT_SECRET", "SNAPCHAT_REDIRECT_URI"), ("publish", "analytics"), True, "snap_public_profile_api"),
        ChannelDefinition("telegram", "Telegram", "telegram", ("TELEGRAM_TOKEN", "KEMET_TELEGRAM_WEBHOOK_SECRET"), ("publish", "webhook"), False, "telegram_bot_token"),
        ChannelDefinition("whatsapp", "WhatsApp", "meta", ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_VERIFY_TOKEN"), ("publish", "webhook", "delivery"), True, "whatsapp_cloud_api"),
        ChannelDefinition("pinterest", "Pinterest", "pinterest", ("PINTEREST_CLIENT_ID", "PINTEREST_CLIENT_SECRET", "PINTEREST_REDIRECT_URI"), ("publish", "analytics"), True, "pinterest_oauth_api"),
        ChannelDefinition("linkedin", "LinkedIn", "linkedin", ("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET", "LINKEDIN_REDIRECT_URI"), ("publish", "analytics"), True, "linkedin_oauth_posts_api"),
        ChannelDefinition("x", "X", "x", ("X_CLIENT_ID", "X_CLIENT_SECRET", "X_REDIRECT_URI"), ("publish", "analytics"), True, "x_oauth_api"),
        ChannelDefinition("threads", "Threads", "meta", ("THREADS_CLIENT_ID", "THREADS_CLIENT_SECRET", "THREADS_REDIRECT_URI"), ("publish", "analytics"), True, "threads_oauth_api"),
    )

    @classmethod
    def snapshot(cls, organization_id: int | None) -> dict[str, Any]:
        channels = []
        catalog = {x["channel_id"]: x for x in social_channel_catalog.snapshot(int(organization_id or 0))["channels"]}
        for channel in cls.CHANNELS:
            configured = all(bool(os.getenv(key, "").strip()) for key in channel.env_keys)
            publishing_authority_verified = False
            access_token_usable = False
            authority_evidence = "configuration_only"
            if channel.channel_id == "youtube":
                state_dir = Path(__file__).resolve().parents[2] / "ops" / "youtube_state"
                token_path = state_dir / "token.json"
                client_path = state_dir / "client_secret.json"
                try:
                    token = json.loads(token_path.read_text(encoding="utf-8"))
                    scope = str(token.get("scope", ""))
                    upload_scope = "https://www.googleapis.com/auth/youtube.upload" in scope.split()
                    has_refresh_token = bool(str(token.get("refresh_token", "")).strip())
                    has_client = client_path.is_file()
                    expiry_ms = float(token.get("expiry_date") or 0)
                    access_token_usable = expiry_ms > (time.time() * 1000) if expiry_ms else False
                    publishing_authority_verified = bool(upload_scope and has_refresh_token and has_client)
                    if publishing_authority_verified and access_token_usable:
                        authority_evidence = "youtube_oauth_upload_scope_active"
                    elif publishing_authority_verified:
                        authority_evidence = "youtube_oauth_upload_scope_refreshable"
                    elif upload_scope:
                        authority_evidence = "youtube_oauth_upload_scope_incomplete"
                    else:
                        authority_evidence = "youtube_read_only_scope"
                except (OSError, ValueError, TypeError):
                    authority_evidence = "youtube_token_unavailable"
            channels.append({
                "id": channel.channel_id, "channel_id": channel.channel_id, "name": channel.name,
                "provider": channel.provider, "configuration": "configured" if configured else "not_configured",
                "configured": configured, "missing_configuration": [key for key in channel.env_keys if not os.getenv(key, "").strip()],
                "connection": "not_connected", "capabilities": list(channel.capabilities),
                "measurement_ready": channel.measurement, "publishing_authority": channel.publishing_authority,
                "publishing_authority_verified": publishing_authority_verified,
                "access_token_usable": access_token_usable,
                "authority_evidence": authority_evidence,
                "publish_state": "approval_required", "credentials_exposed": False,
                "catalog_status": catalog.get(channel.channel_id, {}).get("status", "catalogued"),
            })
        return {
            "version": cls.VERSION, "organization_id": organization_id, "channels": channels,
            "ready_count": sum(c["configuration"] == "configured" for c in channels), "connected_count": 0,
            "governance": {"read_only": True, "tenant_scoped": True, "no_secret_discovery": True,
                           "no_execution_authority": True, "canonical_runtime_only": True,
                           "approval_required_for_publish": True, "login_oauth_is_not_publishing_authority": True},
        }


social_channel_readiness_service = SocialChannelReadinessService()
