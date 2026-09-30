from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import os
import time
from urllib.parse import urlparse

import requests

from app import db
from app.core.ai_federation import ai_federation
from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.secret_boundary import redact, secret_reference
from app.models.provider_connection import ProviderConnectionRecord


LIVE_VERIFY_SUPPORT = {"openai", "anthropic", "google", "xai", "openrouter", "codecraft"}
VALID_STATUSES = {"configured", "verified", "requires_user_action", "revoked", "error", "unsupported"}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    return redact(value or {})


def _safe_ref(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) > 128 or any(x in value.lower() for x in ("key", "token", "secret", "password", "bearer")):
        raise ValueError("unsafe_credential_ref")
    return value


def _live_verify(provider_id: str) -> tuple[bool, int | None]:
    endpoints = {
        "openai": ("https://api.openai.com/v1/models", {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}"}),
        "anthropic": ("https://api.anthropic.com/v1/models", {"x-api-key": os.getenv("ANTHROPIC_API_KEY", ""), "anthropic-version": "2023-06-01"}),
        "google": ("https://generativelanguage.googleapis.com/v1beta/models", {"x-goog-api-key": os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")}),
        "xai": ("https://api.x.ai/v1/models", {"Authorization": f"Bearer {os.getenv('XAI_API_KEY', '')}"}),
        "openrouter": ("https://openrouter.ai/api/v1/models", {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}"}),
        "codecraft": ("https://codecraftapi.com/v1/models", {"Authorization": f"Bearer {os.getenv('CODECRAFT_API_KEY', '')}"}),
    }
    endpoint, headers = endpoints[provider_id]
    host = urlparse(endpoint).hostname
    endpoint = validate_public_http_target(endpoint, allow_hosts={str(host).lower()})
    started = time.monotonic()
    response = governed_request("GET", endpoint, headers=headers, timeout=10, allow_redirects=False)
    response.raise_for_status()
    data = response.json()
    items = data.get("data") if isinstance(data, dict) else None
    if items is None:
        items = data.get("models") if isinstance(data, dict) else None
    count = len(items) if isinstance(items, list) else None
    return True, round((time.monotonic() - started) * 1000)


class ConnectionLifecycleService:
    VERSION = "1.0"

    @staticmethod
    def register(organization_id: int, user_id: int, provider_id: str, mode: str = "api",
                 scopes: list[str] | None = None, metadata: dict[str, Any] | None = None,
                 credential_ref: str | None = None, provider_account_ref: str | None = None,
                 provider_project_ref: str | None = None):
        profile = ai_federation.get(provider_id)
        if not profile and not str(provider_id).startswith("social:"):
            raise ValueError("unsupported_provider")
        if mode not in {"api", "official_connector", "user_handoff"}:
            raise ValueError("unsupported_connection_mode")
        status = "configured" if mode != "user_handoff" and (profile.is_configured() if profile else True) else "requires_user_action"
        if mode == "user_handoff":
            status = "requires_user_action"
        row = ProviderConnectionRecord.query.filter_by(
            organization_id=organization_id, user_id=user_id, provider_id=provider_id, mode=mode
        ).first()
        if not row:
            row = ProviderConnectionRecord(
                organization_id=organization_id, user_id=user_id, provider_id=provider_id, mode=mode
            )
        row.status = status
        row.scopes_json = list(scopes or [])
        row.metadata_json = _safe_metadata(metadata)
        row.credential_ref = _safe_ref(credential_ref)
        row.provider_account_ref = _safe_ref(provider_account_ref)
        row.provider_project_ref = _safe_ref(provider_project_ref)
        row.revoked_at = None
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def verify(row: ProviderConnectionRecord, live: bool = False):
        if row.status == "revoked":
            raise ValueError("connection_revoked")
        if not live:
            row.status = "configured" if row.mode != "user_handoff" else "requires_user_action"
            db.session.commit()
            return {"verified": False, "verification_supported": row.provider_id in LIVE_VERIFY_SUPPORT, "network_call": False}
        if row.provider_id not in LIVE_VERIFY_SUPPORT:
            return {"verified": False, "verification_supported": False, "network_call": False}
        if row.mode == "user_handoff":
            return {"verified": False, "verification_supported": False, "network_call": False}
        if not ai_federation.get(row.provider_id).is_configured():
            row.status = "requires_user_action"
            db.session.commit()
            return {"verified": False, "verification_supported": True, "network_call": False}
        try:
            verified, latency_ms = _live_verify(row.provider_id)
        except (requests.RequestException, ValueError, KeyError, TypeError):
            row.status = "error"
            db.session.commit()
            return {"verified": False, "verification_supported": True, "network_call": True, "error": "provider_verification_failed"}
        row.status = "verified" if verified else "error"
        row.last_verified_at = _now() if verified else row.last_verified_at
        db.session.commit()
        return {"verified": verified, "verification_supported": True, "network_call": True, "latency_ms": latency_ms}

    @staticmethod
    def revoke(row: ProviderConnectionRecord):
        row.status = "revoked"
        row.revoked_at = _now()
        db.session.commit()
        return row

    @staticmethod
    def list_for_user(organization_id: int, user_id: int):
        return ProviderConnectionRecord.query.filter_by(
            organization_id=organization_id, user_id=user_id
        ).order_by(ProviderConnectionRecord.provider_id).all()

    @staticmethod
    def as_public(row: ProviderConnectionRecord) -> dict[str, Any]:
        return {
            "id": row.id, "organization_id": row.organization_id, "user_id": row.user_id,
            "provider_id": row.provider_id, "mode": row.mode, "status": row.status,
            "scopes": list(row.scopes_json or []), "metadata": _safe_metadata(row.metadata_json),
            "provider_account_ref": row.provider_account_ref,
            "provider_project_ref": row.provider_project_ref,
            "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        }
