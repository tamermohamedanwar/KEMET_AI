from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.social_credential_store import social_credential_store
from app.models.provider_connection import ProviderConnectionRecord


@dataclass(frozen=True)
class TikTokResearchRequest:
    organization_id: int
    user_id: int
    keyword: str
    region_code: str = "EG"
    start_date: str = ""
    end_date: str = ""
    max_count: int = 20


class TikTokResearchAdapter:
    VERSION = "1.0"
    ENDPOINT = "https://open.tiktokapis.com/v2/research/video/query/"
    REQUIRED_SCOPE = "research.data.basic"

    def preflight(self, request: TikTokResearchRequest) -> dict[str, Any]:
        if request.organization_id <= 0 or request.user_id <= 0:
            return self._blocked("research_identity_required")
        if not request.keyword.strip():
            return self._blocked("research_keyword_required")
        if not 1 <= request.max_count <= 100:
            return self._blocked("research_max_count_out_of_range")
        connection = self._connection(request)
        if connection is None or connection.status != "verified":
            return self._blocked("research_connection_not_ready")
        metadata = connection.metadata_json or {}
        if metadata.get("research_eligibility") != "approved":
            return self._blocked("tiktok_research_access_requires_approval")
        if metadata.get("research_org_type") != "nonprofit":
            return self._blocked("tiktok_research_not_available_for_commercial_use")
        scopes = set(connection.scopes_json or [])
        if self.REQUIRED_SCOPE not in scopes:
            return self._blocked("research_scope_not_authorized")
        credentials = social_credential_store.get(request.organization_id, request.user_id, "tiktok")
        token = str(credentials.get("client_access_token") or "").strip()
        if not token:
            return self._blocked("research_credentials_missing")
        return {"success": True, "status": "ready", "verified": True, "read_only": True, "execution_authority": False, "credentials_exposed": False}

    def query(self, request: TikTokResearchRequest) -> dict[str, Any]:
        ready = self.preflight(request)
        if not ready.get("success"):
            return ready
        credentials = social_credential_store.get(request.organization_id, request.user_id, "tiktok")
        token = str(credentials.get("client_access_token") or "").strip()
        start_date = request.start_date or "20260101"
        end_date = request.end_date or "20260130"
        endpoint = validate_public_http_target(self.ENDPOINT, allow_hosts={"open.tiktokapis.com"})
        params = {"fields": "id,video_description,create_time,region_code,share_count,view_count,like_count,comment_count,hashtag_names,username,video_duration"}
        body = {"query": {"and": [{"operation": "EQ", "field_name": "keyword", "field_values": [request.keyword.strip()]}, {"operation": "IN", "field_name": "region_code", "field_values": [request.region_code.upper()]}]}, "max_count": request.max_count, "start_date": start_date, "end_date": end_date}
        response = governed_request("POST", endpoint, params=params, json=body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, timeout=30, allow_redirects=False)
        if response.status_code == 429:
            return self._blocked("tiktok_research_rate_limited")
        response.raise_for_status()
        data = response.json().get("data") or {}
        return {"success": True, "status": "measured", "source": "tiktok_research_api", "videos": data.get("videos") or [], "cursor": data.get("cursor"), "search_id": data.get("search_id"), "has_more": bool(data.get("has_more")), "verified": True, "read_only": True, "execution_authority": False, "credentials_exposed": False}

    @staticmethod
    def _connection(request: TikTokResearchRequest):
        return ProviderConnectionRecord.query.filter_by(organization_id=request.organization_id, user_id=request.user_id, provider_id="social:tiktok", mode="official_connector").first()

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "error": error, "verified": False, "read_only": True, "execution_authority": False, "credentials_exposed": False}


tiktok_research_adapter = TikTokResearchAdapter()
