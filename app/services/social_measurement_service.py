from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.social_credential_store import social_credential_store
from app.models.provider_connection import ProviderConnectionRecord


@dataclass(frozen=True)
class MeasurementRequest:
    organization_id: int
    user_id: int
    channel: str
    publication_id: str


class SocialMeasurementService:
    VERSION = "1.0"
    GRAPH = "https://graph.facebook.com/v23.0"

    def measure(self, request: MeasurementRequest) -> dict[str, Any]:
        if request.organization_id <= 0 or request.user_id <= 0 or not request.publication_id.strip():
            return self._blocked("measurement_identity_required")
        if request.channel not in {"facebook", "instagram"}:
            return self._blocked("unsupported_platform")
        connection = ProviderConnectionRecord.query.filter_by(
            organization_id=request.organization_id,
            user_id=request.user_id,
            provider_id=f"social:{request.channel}",
            mode="official_connector",
        ).first()
        if connection is None or connection.status != "verified":
            return self._blocked("measurement_connection_not_ready")
        credentials = social_credential_store.get(request.organization_id, request.user_id, request.channel)
        token = str(credentials.get("page_access_token") or credentials.get("access_token") or "").strip()
        if not token:
            return self._blocked("measurement_credentials_missing")
        if request.channel == "instagram":
            return self._instagram(request.publication_id, token)
        return self._facebook(request.publication_id, token)

    def _instagram(self, publication_id: str, token: str) -> dict[str, Any]:
        metrics = "views,reach,likes,comments,saved,shares,total_interactions"
        return self._fetch_insights("instagram", publication_id, token, metrics)

    def _facebook(self, publication_id: str, token: str) -> dict[str, Any]:
        metrics = "post_impressions,post_reach,post_engaged_users,post_reactions_by_type_total"
        return self._fetch_insights("facebook", publication_id, token, metrics)

    def _fetch_insights(self, channel: str, publication_id: str, token: str, metrics: str) -> dict[str, Any]:
        endpoint = validate_public_http_target(
            f"{self.GRAPH}/{publication_id}/insights",
            allow_hosts={"graph.facebook.com"},
        )
        response = governed_request("GET", 
            endpoint,
            params={"metric": metrics, "access_token": token},
            timeout=30,
            allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
        normalized = self._normalize(payload)
        return {
            "success": True,
            "status": "measured",
            "channel": channel,
            "publication_id": publication_id,
            "metrics": normalized,
            "metric_provenance": {name: "OBSERVED" for name in normalized},
            "verified": True,
            "credentials_exposed": False,
        }

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for item in payload.get("data", []) or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            values_value = item.get("values") or []
            if name and values_value:
                latest = values_value[-1]
                values[name] = latest.get("value") if isinstance(latest, dict) else latest
        return values

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": "blocked",
            "error": error,
            "metrics": {},
            "metric_provenance": {},
            "verified": False,
            "credentials_exposed": False,
        }


social_measurement_service = SocialMeasurementService()
