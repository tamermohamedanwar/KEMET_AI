from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

import requests

from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.execution_evidence import execution_evidence
from app.core.social_credential_store import social_credential_store
from app.models.provider_connection import ProviderConnectionRecord


@dataclass(frozen=True)
class TikTokPublishRequest:
    organization_id: int
    user_id: int
    asset_uri: str
    media_type: str = "video"
    caption: str = ""
    idempotency_key: str = ""
    production_job_id: str = ""
    publication_approval: bool = False
    publication_contract_digest: str = ""
    dry_run: bool = False


class TikTokPublishingAdapter:
    VERSION = "1.0"
    API = "https://open.tiktokapis.com/v2"

    def preflight(self, request: TikTokPublishRequest) -> dict[str, Any]:
        if request.organization_id <= 0 or request.user_id <= 0:
            return self._blocked("identity_scope_required")
        if request.media_type != "video":
            return self._blocked("tiktok_video_required")
        if not request.asset_uri.strip():
            return self._blocked("asset_uri_required")
        connection = self._connection(request)
        if connection is None or connection.status != "verified":
            return self._blocked("publishing_connection_not_ready")
        if not connection.credential_ref or not connection.provider_account_ref:
            return self._blocked("publishing_identity_incomplete")
        credentials = social_credential_store.get(request.organization_id, request.user_id, "tiktok")
        token = str(credentials.get("access_token") or "").strip()
        scopes = self._scopes(credentials, connection.scopes)
        if not token:
            return self._blocked("publishing_credentials_missing")
        if not ({"video.publish", "video.upload"} & set(scopes)):
            return self._blocked("publishing_scope_not_verified")
        creator = self._creator_info(token)
        if not creator.get("open_id"):
            return self._blocked("creator_identity_not_verified")
        return {
            "ready": True,
            "channel": "tiktok",
            "provider_account_ref": connection.provider_account_ref,
            "credential_ref": connection.credential_ref,
            "creator": creator,
            "scopes": scopes,
            "approval_required": True,
            "canonical_runtime_only": True,
            "credentials_exposed": False,
        }

    def publish(self, request: TikTokPublishRequest, *, execution_key: str, plan_hash: str | None = None, approved_execution: bool = False, execution_authorization: dict[str, Any] | None = None) -> dict[str, Any]:
        preflight = self.preflight(request)
        if not preflight.get("ready"):
            return {**preflight, "success": False, "status": "blocked", "executed": False}
        if not execution_key:
            return self._blocked("execution_key_required")
        if not request.dry_run and (approved_execution is not True or not isinstance(execution_authorization, dict)):
            return self._blocked("canonical_runtime_authorization_required")
        if not request.dry_run:
            from app.services.mendes.mendes_publication_contract_service import mendes_publication_contract_service
            publication = mendes_publication_contract_service.validate(organization_id=request.organization_id, production_job_id=request.production_job_id, approval=request.publication_approval)
            if not publication.get("ready"):
                return {**publication, "success": False, "executed": False}
            if request.publication_contract_digest != publication.get("publication_contract_digest"):
                return self._blocked("publication_contract_digest_mismatch")

        idem = request.idempotency_key or self._idempotency(request, execution_key)
        evidence_key = f"{execution_key}:tiktok:publish:{idem}"
        for item in execution_evidence.history(organization_id=request.organization_id, execution_key=execution_key, limit=100):
            if item.get("evidence_key") == evidence_key:
                return {"success": True, "status": "reused", "executed": True, "idempotent": True, "receipt": item.get("receipt", {})}
        if not request.dry_run:
            from app.services.mendes.mendes_publication_contract_service import mendes_publication_contract_service
            publication = mendes_publication_contract_service.validate(organization_id=request.organization_id, production_job_id=request.production_job_id, approval=request.publication_approval)
            if not publication.get("ready"):
                return {**publication, "success": False, "executed": False}
            if request.publication_contract_digest != publication.get("publication_contract_digest"):
                return self._blocked("publication_contract_digest_mismatch")

        if request.dry_run:
            receipt = {"status": "simulated", "provider": "tiktok", "idempotency_key": idem, "asset_uri": request.asset_uri}
            self._record(request, execution_key, evidence_key, plan_hash, receipt, "simulated")
            return {"success": True, "status": "simulated", "executed": False, "receipt": receipt, "evidence_key": evidence_key}
        credentials = social_credential_store.get(request.organization_id, request.user_id, "tiktok")
        token = str(credentials.get("access_token") or "").strip()
        creator = self._creator_info(token)
        if not creator.get("open_id"):
            return self._blocked("creator_identity_not_verified")
        result = self._direct_post(request, token, creator)
        self._record(request, execution_key, evidence_key, plan_hash, result, "submitted")
        return {"success": True, "status": "submitted", "executed": True, "receipt": result, "evidence_key": evidence_key}

    def _direct_post(self, request: TikTokPublishRequest, token: str, creator: dict[str, Any]) -> dict[str, Any]:
        endpoint = validate_public_http_target(f"{self.API}/post/publish/video/init/", allow_hosts={"open.tiktokapis.com"})
        payload = {
            "post_info": {"title": request.caption[:2200], "privacy_level": self._privacy_level(creator), "disable_duet": False, "disable_comment": False, "disable_stitch": False},
            "source_info": {"source": "PULL_FROM_URL", "video_url": request.asset_uri},
        }
        response = governed_request("POST", endpoint, json=payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, timeout=60, allow_redirects=False)
        if response.status_code == 429:
            raise RuntimeError("tiktok_rate_limited")
        response.raise_for_status()
        data = response.json().get("data") or {}
        publish_id = data.get("publish_id")
        if not publish_id:
            raise RuntimeError("tiktok_publish_receipt_missing")
        return {"provider": "tiktok", "publication_id": str(publish_id), "open_id": str(creator.get("open_id")), "idempotency_key": request.idempotency_key or "derived", "privacy_level": self._privacy_level(creator), "provider_status": "submitted"}

    def fetch_status(self, token: str, publish_id: str) -> dict[str, Any]:
        if not token or not publish_id:
            return self._blocked("tiktok_status_identity_required")
        endpoint = validate_public_http_target(f"{self.API}/post/publish/status/fetch/", allow_hosts={"open.tiktokapis.com"})
        response = governed_request("POST", endpoint, json={"publish_id": publish_id}, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, timeout=30, allow_redirects=False)
        if response.status_code == 429:
            return self._blocked("tiktok_rate_limited")
        response.raise_for_status()
        data = response.json().get("data") or {}
        status = str(data.get("status") or "UNKNOWN")
        return {"success": True, "status": status.lower(), "provider_status": status, "publication_id": publish_id, "publicly_available_post_id": data.get("publicaly_available_post_id"), "verified": status in {"PUBLISH_COMPLETE", "FAILED"}, "credentials_exposed": False}

    def _creator_info(self, token: str) -> dict[str, Any]:
        endpoint = validate_public_http_target(f"{self.API}/post/publish/creator_info/query/", allow_hosts={"open.tiktokapis.com"})
        response = governed_request("POST", endpoint, json={}, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, timeout=30, allow_redirects=False)
        if response.status_code == 429:
            raise RuntimeError("tiktok_rate_limited")
        response.raise_for_status()
        return dict(response.json().get("data") or {})

    @staticmethod
    def _privacy_level(creator: dict[str, Any]) -> str:
        options = [str(x) for x in creator.get("privacy_level_options") or []]
        if not options:
            raise RuntimeError("tiktok_privacy_options_missing")
        return "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in options else options[0]

    @staticmethod
    def _scopes(credentials: dict[str, Any], connection_scopes: Any) -> list[str]:
        raw = credentials.get("scope") or credentials.get("scopes") or connection_scopes or []
        if isinstance(raw, str):
            return sorted({x for x in raw.replace(",", " ").split() if x})
        return sorted({str(x) for x in raw}) if isinstance(raw, list) else []

    @staticmethod
    def _connection(request: TikTokPublishRequest) -> ProviderConnectionRecord | None:
        return ProviderConnectionRecord.query.filter_by(organization_id=request.organization_id, user_id=request.user_id, provider_id="social:tiktok", mode="official_connector").first()

    @staticmethod
    def _idempotency(request: TikTokPublishRequest, execution_key: str) -> str:
        raw = json.dumps({"execution_key": execution_key, "asset_uri": request.asset_uri, "caption": request.caption}, sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode()).hexdigest()

    @staticmethod
    def _record(request: TikTokPublishRequest, execution_key: str, evidence_key: str, plan_hash: str | None, receipt: dict[str, Any], status: str) -> None:
        execution_evidence.record(organization_id=request.organization_id, execution_key=execution_key, stage="channel.tiktok.publish", status=status, evidence_key=evidence_key, plan_hash=plan_hash, receipt=receipt)

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "error": error, "executed": False, "credentials_exposed": False}


tiktok_publishing_adapter = TikTokPublishingAdapter()
