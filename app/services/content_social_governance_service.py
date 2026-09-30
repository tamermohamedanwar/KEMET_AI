from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ContentAssetContract:
    organization_id: int
    content_id: str
    version: int
    content_type: str
    language: str
    canonical_digest: str
    lifecycle_state: str = "DRAFT"
    canonical_payload: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "kemet.content_asset.v1",
            "organization_id": self.organization_id,
            "content_id": self.content_id,
            "version": self.version,
            "content_type": self.content_type,
            "language": self.language,
            "canonical_digest": self.canonical_digest,
            "lifecycle_state": self.lifecycle_state,
            "canonical_payload": dict(self.canonical_payload or {}),
        }


@dataclass(frozen=True)
class ContentApprovalContract:
    organization_id: int
    content_id: str
    approved_version: int
    content_digest: str
    approver_id: str
    state: str = "APPROVED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "kemet.content_approval.v1",
            "organization_id": self.organization_id,
            "content_id": self.content_id,
            "approved_version": self.approved_version,
            "content_digest": self.content_digest,
            "approver_id": self.approver_id,
            "state": self.state,
        }


@dataclass(frozen=True)
class PublishingIntentContract:
    organization_id: int
    intent_id: str
    content_id: str
    content_version: int
    content_digest: str
    platform: str
    account_ref: str
    idempotency_key: str
    risk_tier: str = "high"
    status: str = "PENDING_APPROVAL"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "kemet.publishing_intent.v1",
            "organization_id": self.organization_id,
            "intent_id": self.intent_id,
            "content_id": self.content_id,
            "content_version": self.content_version,
            "content_digest": self.content_digest,
            "platform": self.platform,
            "account_ref": self.account_ref,
            "idempotency_key": self.idempotency_key,
            "risk_tier": self.risk_tier,
            "status": self.status,
        }


class ContentSocialGovernanceService:
    VERSION = "1.0"
    PLATFORMS = ("instagram", "facebook", "tiktok", "youtube", "linkedin")
    STATES = ("DRAFT", "READY_FOR_REVIEW", "APPROVED", "REJECTED", "SUPERSEDED", "PUBLISHING_REQUESTED", "PUBLISHED", "FAILED")
    EVIDENCE_STATES = ("supported", "unsupported", "needs_review", "not_applicable")
    MAX_LENGTHS = {"objective": 240, "audience": 500, "topic": 240, "angle": 240, "key_message": 500, "hook": 240, "body": 8000, "caption": 4000, "cta": 500}
    CONNECTOR_STATES = ("DISCOVERED", "CONFIGURED", "AUTHENTICATED", "VERIFIED", "READY", "DEGRADED", "DISCONNECTED", "BLOCKED")

    def build_asset(self, *, organization_id: int, content_id: str, version: int,
                    content_type: str, language: str, payload: Mapping[str, Any],
                    lifecycle_state: str = "DRAFT") -> dict[str, Any]:
        self._org(organization_id)
        if version <= 0:
            raise ValueError("content_version_required")
        if lifecycle_state not in self.STATES:
            raise ValueError("invalid_content_state")
        digest = self._digest(payload)
        canonical_payload = dict(payload)
        return ContentAssetContract(int(organization_id), str(content_id), int(version), str(content_type), str(language), digest, lifecycle_state, canonical_payload).as_dict()

    def validate_asset(self, *, asset: Mapping[str, Any], tenant_id: int) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        def check(name: str, passed: bool, error: str) -> None:
            checks.append({"name": name, "passed": bool(passed), "error": None if passed else error})
        required = ("content_id", "organization_id", "version", "canonical_digest", "content_type", "language", "objective", "audience", "topic", "key_message", "hook", "body", "content_type", "target_platforms")
        for key in required:
            check(f"required:{key}", bool(str(asset.get(key) or "").strip()), f"{key}_required")
        check("tenant", int(asset.get("organization_id") or 0) == int(tenant_id), "tenant_mismatch")
        check("version", int(asset.get("version") or 0) > 0, "content_version_required")
        platforms = [str(x).strip().lower() for x in (asset.get("target_platforms") or [])]
        check("platforms", bool(platforms) and all(x in self.PLATFORMS for x in platforms), "unsupported_platform")
        for key, limit in self.MAX_LENGTHS.items():
            value = str(asset.get(key) or "")
            if value:
                check(f"length:{key}", len(value) <= limit, f"{key}_too_long")
        claims = asset.get("claims") or []
        if isinstance(claims, Mapping):
            claims = claims.get("items") or []
        claim_states = {str((item or {}).get("evidence_state") or "needs_review") for item in claims if isinstance(item, Mapping)}
        check("claims_evidence", not ("unsupported" in claim_states), "unsupported_claim")
        check("claim_states", claim_states.issubset(set(self.EVIDENCE_STATES)), "invalid_evidence_state")
        canonical_payload = asset.get("canonical_payload")
        digest = self._digest(canonical_payload) if isinstance(canonical_payload, Mapping) else ""
        check("digest", bool(digest) and str(asset.get("canonical_digest")) == digest, "canonical_digest_mismatch")
        return {"valid": all(item["passed"] for item in checks), "checks": checks, "errors": [item["error"] for item in checks if item["error"]]}

    def create_approval(self, *, asset: Mapping[str, Any], approver_id: str) -> dict[str, Any]:
        if int(asset.get("organization_id") or 0) <= 0:
            raise ValueError("organization_required")
        if int(asset.get("version") or 0) <= 0 or not asset.get("canonical_digest"):
            raise ValueError("content_binding_required")
        if not str(approver_id or "").strip():
            raise ValueError("approver_required")
        return ContentApprovalContract(
            int(asset["organization_id"]), str(asset["content_id"]), int(asset["version"]),
            str(asset["canonical_digest"]), str(approver_id),
        ).as_dict()

    def create_publishing_intent(self, *, asset: Mapping[str, Any], platform: str,
                                 account_ref: str, idempotency_key: str) -> dict[str, Any]:
        platform = str(platform or "").strip().lower()
        if platform not in self.PLATFORMS:
            raise ValueError("unsupported_platform")
        if asset.get("lifecycle_state") != "APPROVED":
            raise ValueError("approved_content_required")
        if not str(account_ref or "").strip():
            raise ValueError("target_account_required")
        if not str(idempotency_key or "").strip():
            raise ValueError("idempotency_key_required")
        seed = {
            "organization_id": int(asset["organization_id"]),
            "content_id": str(asset["content_id"]),
            "version": int(asset["version"]),
            "digest": str(asset["canonical_digest"]),
            "platform": platform,
            "account_ref": str(account_ref),
            "idempotency_key": str(idempotency_key),
        }
        intent_id = "pi_" + self._digest(seed)[:40]
        return PublishingIntentContract(
            int(asset["organization_id"]), intent_id, str(asset["content_id"]),
            int(asset["version"]), str(asset["canonical_digest"]), platform,
            str(account_ref), str(idempotency_key),
        ).as_dict()

    def validate_approval_for_publish(self, *, asset: Mapping[str, Any], approval: Mapping[str, Any]) -> dict[str, Any]:
        checks = {
            "tenant": int(asset.get("organization_id") or 0) == int(approval.get("organization_id") or 0),
            "content_id": str(asset.get("content_id")) == str(approval.get("content_id")),
            "version": int(asset.get("version") or 0) == int(approval.get("approved_version") or 0),
            "digest": str(asset.get("canonical_digest")) == str(approval.get("content_digest")),
            "state": str(approval.get("state")) == "APPROVED",
            "asset_state": str(asset.get("lifecycle_state")) == "APPROVED",
        }
        return {"valid": all(checks.values()), "checks": checks, "external_execution": False}

    @classmethod
    def connector_state(cls, *, configured: bool, authenticated: bool, verified: bool,
                        healthy: bool = True) -> str:
        if not configured:
            return "DISCOVERED"
        if not authenticated:
            return "CONFIGURED"
        if not verified:
            return "AUTHENTICATED"
        if not healthy:
            return "DEGRADED"
        return "READY"

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _org(value: Any) -> None:
        if int(value or 0) <= 0:
            raise ValueError("organization_required")


content_social_governance_service = ContentSocialGovernanceService()
