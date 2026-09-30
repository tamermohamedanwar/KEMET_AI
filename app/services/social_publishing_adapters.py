from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import time
from typing import Any

import requests

from app.core.evidence import execution_evidence_fabric
from app.core.execution_evidence import execution_evidence
from app.core.secret_boundary import redact
from app.core.social_credential_store import social_credential_store
from app.models.provider_connection import ProviderConnectionRecord


@dataclass(frozen=True)
class PublishRequest:
    organization_id: int
    user_id: int
    channel: str
    asset_uri: str
    media_type: str
    caption: str = ""
    title: str = ""
    idempotency_key: str = ""
    production_job_id: str = ""
    publication_approval: bool = False
    publication_contract_digest: str = ""
    content_id: str = ""
    content_version: int = 0
    content_digest: str = ""
    dry_run: bool = False


class SocialPublishingAdapter:
    VERSION = "1.0"

    def preflight(self, request: PublishRequest) -> dict[str, Any]:
        if request.organization_id <= 0 or request.user_id <= 0:
            return self._blocked("identity_scope_required")
        if request.channel not in {"facebook", "instagram"}:
            return self._blocked("unsupported_platform")
        if not request.asset_uri.strip():
            return self._blocked("asset_uri_required")
        if request.media_type not in {"image", "video"}:
            return self._blocked("unsupported_media_type")
        connection = self._connection(request)
        if connection is None or connection.status != "verified":
            return self._blocked("publishing_connection_not_ready")
        if not connection.credential_ref or not connection.provider_account_ref:
            return self._blocked("publishing_identity_incomplete")
        metadata = connection.metadata_json if isinstance(connection.metadata_json, dict) else {}
        if metadata.get("publishing_capable") is not True:
            return self._blocked("publishing_capability_not_verified")
        return {
            "ready": True,
            "channel": request.channel,
            "provider_account_ref": connection.provider_account_ref,
            "credential_ref": connection.credential_ref,
            "approval_required": True,
            "canonical_runtime_only": True,
            "credentials_exposed": False,
        }

    def publish(self, request: PublishRequest, *, execution_key: str, plan_hash: str | None = None, approved_execution: bool = False, execution_authorization: dict[str, Any] | None = None) -> dict[str, Any]:
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

        account_ref = str(preflight.get("provider_account_ref") or "")
        idem = request.idempotency_key or self._idempotency(request, execution_key, account_ref)
        evidence_key = self._evidence_key(request, account_ref, idem)
        if not request.dry_run:
            from app.models.execution_evidence import ExecutionEvidence
            existing_row = ExecutionEvidence.query.filter_by(
                organization_id=request.organization_id, evidence_key=evidence_key
            ).first()
            if existing_row is not None:
                return {"success": True, "status": "reused", "executed": True, "idempotent": True, "receipt": json.loads(existing_row.receipt_json or "{}"), "evidence_key": evidence_key}
        if not request.dry_run:
            from app.services.mendes.mendes_publication_contract_service import mendes_publication_contract_service
            publication = mendes_publication_contract_service.validate(organization_id=request.organization_id, production_job_id=request.production_job_id, approval=request.publication_approval)
            if not publication.get("ready"):
                return {**publication, "success": False, "executed": False}
            if request.publication_contract_digest != publication.get("publication_contract_digest"):
                return self._blocked("publication_contract_digest_mismatch")

        if request.dry_run:
            receipt = {"status": "simulated", "provider": request.channel, "idempotency_key": idem, "asset_uri": request.asset_uri}
            self._record(request, execution_key, evidence_key, plan_hash, receipt, "simulated")
            return {"success": True, "status": "simulated", "executed": False, "receipt": receipt, "evidence_key": evidence_key}
        credentials = social_credential_store.get(request.organization_id, request.user_id, request.channel)
        try:
            if request.channel == "facebook":
                receipt = self._facebook(request, credentials, idem)
            else:
                receipt = self._instagram(request, credentials, idem)
        except requests.Timeout:
            receipt = {"provider": request.channel, "idempotency_key": idem, "outcome": "unknown", "error_classification": "timeout"}
            self._record(request, execution_key, evidence_key, plan_hash, receipt, "ambiguous")
            return {"success": False, "status": "ambiguous", "executed": False, "reconciliation_required": True, "receipt": receipt, "evidence_key": evidence_key}
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            classification = "provider_rejected" if status_code and 400 <= status_code < 500 else "provider_unavailable"
            receipt = {"provider": request.channel, "idempotency_key": idem, "outcome": "unknown" if status_code is None else "rejected", "error_classification": classification, "provider_status": status_code}
            self._record(request, execution_key, evidence_key, plan_hash, receipt, "ambiguous" if status_code is None else "rejected")
            return {"success": False, "status": "ambiguous" if status_code is None else "rejected", "executed": False, "reconciliation_required": status_code is None, "receipt": receipt, "evidence_key": evidence_key}
        except RuntimeError as exc:
            receipt = {"provider": request.channel, "idempotency_key": idem, "outcome": "failed", "error_classification": str(exc)[:120]}
            self._record(request, execution_key, evidence_key, plan_hash, receipt, "failed")
            return {"success": False, "status": "failed", "executed": False, "receipt": receipt, "evidence_key": evidence_key}
        self._record(request, execution_key, evidence_key, plan_hash, receipt, "published")
        return {"success": True, "status": "published", "executed": True, "receipt": receipt, "evidence_key": evidence_key}

    def _facebook(self, request: PublishRequest, credentials: dict[str, Any], idem: str) -> dict[str, Any]:
        page_id = str(credentials.get("page_id") or "").strip()
        page_token = str(credentials.get("page_access_token") or "").strip()
        if not page_id or not page_token:
            raise RuntimeError("facebook_page_publish_credentials_missing")
        base = f"https://graph.facebook.com/v23.0/{page_id}"
        if request.media_type == "image":
            endpoint = f"{base}/photos"
            payload = {"url": request.asset_uri, "caption": request.caption, "access_token": page_token}
        elif request.media_type == "video":
            endpoint = f"{base}/videos"
            payload = {"file_url": request.asset_uri, "description": request.caption, "access_token": page_token}
        else:
            raise RuntimeError("facebook_media_type_unsupported")
        response = requests.post(endpoint, data=payload, timeout=60, allow_redirects=False)
        response.raise_for_status()
        data = response.json()
        provider_id = data.get("post_id") or data.get("id")
        if not provider_id:
            raise RuntimeError("facebook_publish_receipt_missing")
        return {"provider": "facebook", "page_id": page_id, "publication_id": str(provider_id), "idempotency_key": idem, "media_type": request.media_type}

    def _instagram(self, request: PublishRequest, credentials: dict[str, Any], idem: str) -> dict[str, Any]:
        ig_id = str(credentials.get("instagram_account_id") or "").strip()
        access_token = str(credentials.get("page_access_token") or credentials.get("access_token") or "").strip()
        if not ig_id or not access_token:
            raise RuntimeError("instagram_publish_credentials_missing")
        base = f"https://graph.facebook.com/v23.0/{ig_id}"
        payload = {"caption": request.caption, "access_token": access_token}
        if request.media_type == "image":
            payload.update({"image_url": request.asset_uri})
        elif request.media_type == "video":
            payload.update({"media_type": "REELS", "video_url": request.asset_uri})
        else:
            raise RuntimeError("instagram_media_type_unsupported")
        create = requests.post(f"{base}/media", data=payload, timeout=60, allow_redirects=False)
        create.raise_for_status()
        container = create.json().get("id")
        if not container:
            raise RuntimeError("instagram_media_container_missing")
        if request.media_type == "video":
            self._wait_for_instagram_container(container, access_token)
        publish = requests.post(f"{base}/media_publish", data={"creation_id": container, "access_token": access_token}, timeout=60, allow_redirects=False)
        publish.raise_for_status()
        publication_id = publish.json().get("id")
        if not publication_id:
            raise RuntimeError("instagram_publish_receipt_missing")
        return {"provider": "instagram", "instagram_account_id": ig_id, "publication_id": str(publication_id), "container_id": str(container), "idempotency_key": idem, "media_type": request.media_type}

    @staticmethod
    def _wait_for_instagram_container(container_id: str, access_token: str, timeout_seconds: int = 300) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            response = requests.get(f"https://graph.facebook.com/v23.0/{container_id}", params={"fields": "status_code,status", "access_token": access_token}, timeout=30, allow_redirects=False)
            response.raise_for_status()
            data = response.json()
            status = str(data.get("status_code") or data.get("status") or "").upper()
            if status in {"FINISHED", "PUBLISHED"}:
                return
            if status in {"ERROR", "EXPIRED", "FAILED"}:
                raise RuntimeError("instagram_media_container_failed")
            time.sleep(2)
        raise RuntimeError("instagram_media_container_timeout")

    def _connection(self, request: PublishRequest) -> ProviderConnectionRecord | None:
        return ProviderConnectionRecord.query.filter_by(
            organization_id=request.organization_id,
            user_id=request.user_id,
            provider_id=f"social:{request.channel}",
            mode="official_connector",
        ).first()

    def _record(self, request: PublishRequest, execution_key: str, evidence_key: str, plan_hash: str | None, receipt: dict[str, Any], status: str) -> None:
        execution_evidence.record(
            organization_id=request.organization_id,
            execution_key=execution_key,
            stage=f"channel.{request.channel}.publish",
            status=status,
            evidence_key=evidence_key,
            plan_hash=plan_hash,
            receipt=receipt,
        )

    @staticmethod
    def _idempotency(request: PublishRequest, execution_key: str, account_ref: str) -> str:
        payload = {"organization_id": request.organization_id, "content_id": request.content_id, "content_version": request.content_version, "content_digest": request.content_digest, "channel": request.channel, "account_ref": account_ref, "asset_uri": request.asset_uri, "caption": request.caption, "media_type": request.media_type, "explicit_key": request.idempotency_key}
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _evidence_key(request: PublishRequest, account_ref: str, idem: str) -> str:
        return f"social_publish:{request.channel}:{account_ref}:{request.content_id}:{request.content_version}:{request.content_digest}:{idem}"[:512]

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "error": error, "executed": False, "credentials_exposed": False}


social_publishing_adapter = SocialPublishingAdapter()
