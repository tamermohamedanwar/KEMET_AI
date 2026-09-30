from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from app import db
from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.federation.connection_lifecycle import ConnectionLifecycleService
from app.core.secret_boundary import redact
from app.core.social_credential_store import social_credential_store
from app.core.social_oauth_lifecycle import social_oauth_lifecycle


@dataclass(frozen=True)
class ConnectionSpec:
    channel: str
    provider: str
    authorize_url: str
    token_url: str
    client_key_env: str
    client_secret_env: str
    redirect_env: str
    scopes_env: str


class SocialConnectionService:
    VERSION = "2.0"
    SPECS = {
        "youtube": ConnectionSpec("youtube", "google", "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "YOUTUBE_PUBLISH_SCOPES"),
        "tiktok": ConnectionSpec("tiktok", "tiktok", "https://www.tiktok.com/v2/auth/authorize/", "https://open.tiktokapis.com/v2/oauth/token/", "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REDIRECT_URI", "TIKTOK_PUBLISH_SCOPES"),
        "instagram": ConnectionSpec("instagram", "meta", "https://www.facebook.com/v23.0/dialog/oauth", "https://graph.facebook.com/v23.0/oauth/access_token", "INSTAGRAM_CLIENT_ID", "INSTAGRAM_CLIENT_SECRET", "INSTAGRAM_REDIRECT_URI", "META_PUBLISH_SCOPES"),
        "facebook": ConnectionSpec("facebook", "meta", "https://www.facebook.com/v23.0/dialog/oauth", "https://graph.facebook.com/v23.0/oauth/access_token", "FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_SECRET", "FACEBOOK_REDIRECT_URI", "META_PUBLISH_SCOPES"),
    }

    def authorize(self, organization_id: int, user_id: int, channel: str) -> dict[str, Any]:
        spec = self.SPECS.get(str(channel).lower())
        if not organization_id or not user_id or not spec:
            raise ValueError("oauth_scope_or_channel_invalid")
        client_id = os.getenv(spec.client_key_env, "").strip()
        redirect_uri = os.getenv(spec.redirect_env, "").strip()
        scopes = os.getenv(spec.scopes_env, "").strip()
        missing = [k for k, v in ((spec.client_key_env, client_id), (spec.client_secret_env, os.getenv(spec.client_secret_env, "").strip()), (spec.redirect_env, redirect_uri), (spec.scopes_env, scopes)) if not v]
        if missing:
            return {"status": "setup_required", "channel": spec.channel, "provider": spec.provider, "missing_configuration": missing, "credentials_exposed": False}
        state = social_oauth_lifecycle.create_state(int(organization_id), int(user_id), spec.channel)
        payload = social_oauth_lifecycle.authorization_payload(spec.channel, client_id, redirect_uri, scopes, state)
        if spec.provider == "tiktok":
            payload["client_key"] = payload.pop("client_id")
        return {"status": "authorization_ready", "channel": spec.channel, "provider": spec.provider, "authorization_url": social_oauth_lifecycle.build_url(spec.authorize_url, payload), "credentials_exposed": False, "execution_authority": False, "approval_required_for_publish": True}

    def callback(self, organization_id: int, user_id: int, channel: str, code: str, state: str) -> dict[str, Any]:
        spec = self.SPECS.get(str(channel).lower())
        if not spec or not code or not state:
            raise ValueError("oauth_callback_invalid")
        social_oauth_lifecycle.consume_state(state, int(organization_id), int(user_id), spec.channel)
        token = self._exchange(spec, code)
        if spec.provider == "google" and not token.get("refresh_token"):
            raise ValueError("oauth_refresh_token_missing")
        identity = self._verify_identity(spec, token)
        scopes = self._scopes(token, os.getenv(spec.scopes_env, ""))
        if not identity.get("account_ref") or not identity.get("publishing_capable"):
            raise ValueError("publishing_capability_not_verified")
        credential_ref = social_credential_store.put(int(organization_id), int(user_id), spec.channel, token)
        row = ConnectionLifecycleService.register(int(organization_id), int(user_id), f"social:{spec.channel}", mode="official_connector", scopes=scopes, metadata={"purpose": "content_publishing", "provider": spec.provider, "account_name": identity.get("account_name"), "publishing_capable": True}, credential_ref=credential_ref, provider_account_ref=identity.get("account_ref"))
        row.status = "verified"
        row.last_verified_at = __import__("datetime").datetime.utcnow()
        db.session.commit()
        return {"status": "verified", "channel": spec.channel, "provider": spec.provider, "account": identity, "scopes": scopes, "credential_ref": credential_ref, "credentials_exposed": False, "execution_authority": False, "approval_required_for_publish": True}

    def _exchange(self, spec: ConnectionSpec, code: str) -> dict[str, Any]:
        client_id = os.getenv(spec.client_key_env, "").strip()
        client_secret = os.getenv(spec.client_secret_env, "").strip()
        redirect_uri = os.getenv(spec.redirect_env, "").strip()
        endpoint = validate_public_http_target(spec.token_url, allow_hosts={"open.tiktokapis.com", "graph.facebook.com", "oauth2.googleapis.com"})
        if spec.provider == "tiktok":
            response = governed_request("POST", endpoint, data={"client_key": client_id, "client_secret": client_secret, "code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri}, timeout=15, allow_redirects=False)
        elif spec.provider == "google":
            response = governed_request("POST", endpoint, data={"client_id": client_id, "client_secret": client_secret, "code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri}, timeout=15, allow_redirects=False)
        else:
            response = governed_request("GET", endpoint, params={"client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "code": code}, timeout=15, allow_redirects=False)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not data.get("access_token"):
            raise ValueError("oauth_token_exchange_failed")
        if spec.provider == "google":
            if not data.get("refresh_token"):
                data["refresh_token_missing_at_exchange"] = True
            data["oauth_exchange_verified"] = True
        return data

    def _verify_identity(self, spec: ConnectionSpec, token: dict[str, Any]) -> dict[str, Any]:
        access_token = token.get("access_token")
        if spec.provider == "google":
            endpoint = validate_public_http_target("https://www.googleapis.com/youtube/v3/channels", allow_hosts={"www.googleapis.com"})
            response = governed_request("GET", endpoint, params={"part": "id,snippet", "mine": "true"}, headers={"Authorization": f"Bearer {access_token}"}, timeout=15, allow_redirects=False)
            response.raise_for_status()
            items = response.json().get("items", [])
            if not items:
                return {"account_ref": None, "account_name": None, "publishing_capable": False}
            channel = items[0]
            scopes = self._scopes(token, os.getenv(spec.scopes_env, ""))
            return {"account_ref": channel.get("id"), "account_name": (channel.get("snippet") or {}).get("title"), "publishing_capable": "https://www.googleapis.com/auth/youtube.upload" in scopes}
        if spec.provider == "tiktok":
            endpoint = validate_public_http_target("https://open.tiktokapis.com/v2/user/info/", allow_hosts={"open.tiktokapis.com"})
            response = governed_request("GET", endpoint, params={"fields": "open_id,display_name"}, headers={"Authorization": f"Bearer {access_token}"}, timeout=15, allow_redirects=False)
            response.raise_for_status()
            data = response.json().get("data", {}).get("user", {})
            scopes = self._scopes(token, os.getenv(spec.scopes_env, ""))
            return {"account_ref": data.get("open_id"), "account_name": data.get("display_name"), "publishing_capable": "video.publish" in scopes or "video.upload" in scopes}
        endpoint = validate_public_http_target("https://graph.facebook.com/v23.0/me", allow_hosts={"graph.facebook.com"})
        response = governed_request("GET", endpoint, params={"fields": "id,name", "access_token": access_token}, timeout=15, allow_redirects=False)
        response.raise_for_status()
        me = response.json()
        if spec.channel == "facebook":
            pages = governed_request("GET", "https://graph.facebook.com/v23.0/me/accounts", params={"fields": "id,name,access_token,instagram_business_account", "access_token": access_token}, timeout=15, allow_redirects=False)
            pages.raise_for_status()
            items = pages.json().get("data", [])
            if not items:
                return {"account_ref": None, "account_name": me.get("name"), "publishing_capable": False}
            page = items[0]
            page_token = page.get("access_token")
            if page_token:
                token["page_access_token"] = page_token
                token["page_id"] = page.get("id")
            return {"account_ref": page.get("id"), "account_name": page.get("name"), "publishing_capable": bool(page_token)}
        pages = governed_request("GET", "https://graph.facebook.com/v23.0/me/accounts", params={"fields": "id,name,access_token,instagram_business_account", "access_token": access_token}, timeout=15, allow_redirects=False)
        pages.raise_for_status()
        for page in pages.json().get("data", []):
            ig = page.get("instagram_business_account") or {}
            if ig.get("id"):
                page_token = page.get("access_token")
                if page_token:
                    token["page_access_token"] = page_token
                    token["page_id"] = page.get("id")
                    token["instagram_account_id"] = ig.get("id")
                return {"account_ref": ig.get("id"), "account_name": page.get("name"), "publishing_capable": bool(page_token)}
        return {"account_ref": None, "account_name": me.get("name"), "publishing_capable": False}

    @staticmethod
    def _scopes(token: dict[str, Any], configured: str) -> list[str]:
        raw = token.get("scope") or token.get("scopes") or configured
        if isinstance(raw, str):
            return sorted({x for x in raw.replace(",", " ").split() if x})
        if isinstance(raw, list):
            return sorted({str(x) for x in raw})
        return []

    def snapshot(self) -> dict[str, Any]:
        return {"version": self.VERSION, "channels": {channel: {"oauth": "available" if all(os.getenv(key, "").strip() for key in (spec.client_key_env, spec.client_secret_env, spec.redirect_env, spec.scopes_env)) else "setup_required", "lifecycle": ["state", "callback", "token_exchange", "encrypted_store", "account_verification", "publishing_capability"], "publishing_oauth_distinct_from_login": True} for channel, spec in self.SPECS.items()}, "credentials_exposed": False, "execution_authority": False, "canonical_runtime_only": True}


social_connection_service = SocialConnectionService()
