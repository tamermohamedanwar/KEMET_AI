from __future__ import annotations

import os
from typing import Any

from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.social_credential_store import social_credential_store


class GoogleOAuthTokenService:
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def refresh_social_credential(self, organization_id: int, user_id: int, channel: str) -> dict[str, Any]:
        credentials = social_credential_store.get(organization_id, user_id, channel)
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise ValueError("google_refresh_token_missing")
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            raise ValueError("google_oauth_client_configuration_missing")
        endpoint = validate_public_http_target(self.TOKEN_URL, allow_hosts={"oauth2.googleapis.com"})
        response = governed_request(
            "POST",
            endpoint,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
            allow_redirects=False,
        )
        response.raise_for_status()
        refreshed = response.json()
        access_token = refreshed.get("access_token")
        if not access_token:
            raise ValueError("google_refresh_response_missing_access_token")
        updated = dict(credentials)
        updated.update(refreshed)
        updated["refresh_token"] = refresh_token
        social_credential_store.put(organization_id, user_id, channel, updated)
        return {"access_token": access_token, "token_type": refreshed.get("token_type"), "expires_in": refreshed.get("expires_in"), "scope": refreshed.get("scope") or credentials.get("scope")}


google_oauth_token_service = GoogleOAuthTokenService()
