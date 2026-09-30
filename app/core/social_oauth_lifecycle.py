from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Any
from urllib.parse import urlencode

from app import db
from app.models.social_oauth import SocialOAuthState


class SocialOAuthLifecycle:
    VERSION = "1.0"
    TTL_SECONDS = 600

    @staticmethod
    def create_state(organization_id: int, user_id: int, channel: str) -> str:
        if not organization_id or not user_id or not channel:
            raise ValueError("oauth_scope_required")
        raw = secrets.token_urlsafe(48)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        row = SocialOAuthState(
            state_digest=digest, organization_id=organization_id, user_id=user_id,
            channel=channel, purpose="content_publishing",
            expires_at=datetime.utcnow() + timedelta(seconds=SocialOAuthLifecycle.TTL_SECONDS),
        )
        db.session.add(row)
        db.session.commit()
        return raw

    @staticmethod
    def consume_state(state: str, organization_id: int, user_id: int, channel: str) -> SocialOAuthState:
        if not state or not organization_id or not user_id:
            raise ValueError("oauth_state_required")
        digest = hashlib.sha256(state.encode()).hexdigest()
        row = SocialOAuthState.query.filter_by(state_digest=digest).first()
        now = datetime.utcnow()
        if not row or row.organization_id != organization_id or row.user_id != user_id or row.channel != channel:
            raise ValueError("oauth_state_mismatch")
        if row.consumed_at is not None:
            raise ValueError("oauth_state_replayed")
        if row.expires_at <= now:
            raise ValueError("oauth_state_expired")
        row.consumed_at = now
        db.session.commit()
        return row

    @staticmethod
    def authorization_payload(channel: str, client_id: str, redirect_uri: str, scope: str, state: str) -> dict[str, Any]:
        return {
            "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
            "scope": scope, "state": state,
            "access_type": "offline", "include_granted_scopes": "true",
            "prompt": "consent",
            "channel": channel, "purpose": "content_publishing",
            "approval_required_for_publish": True, "execution_authority": False,
        }

    @staticmethod
    def build_url(base_url: str, payload: dict[str, Any]) -> str:
        params = {k: v for k, v in payload.items() if k not in {"channel", "purpose", "approval_required_for_publish", "execution_authority"}}
        return f"{base_url}?{urlencode(params)}"


social_oauth_lifecycle = SocialOAuthLifecycle()
