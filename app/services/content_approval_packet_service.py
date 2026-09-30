from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


class ContentApprovalPacketService:
    VERSION = "1.0"
    SCHEMA = "kemet.content.approval_packet.v1"

    def build(
        self,
        *,
        organization_id: int,
        experiment: Mapping[str, Any],
        production_brief: Mapping[str, Any],
        production_result: Mapping[str, Any],
    ) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        self._bind(org, experiment, production_brief, production_result)
        readiness = production_result.get("readiness") or {}
        artifact = production_result.get("artifact") or {}
        verification = production_result.get("verification") or {}
        rights = readiness.get("rights_review") or {}
        quality = readiness.get("quality_gates") or {}
        voice = readiness.get("voice_review") or {}
        evidence = {
            "quality": self._quality_evidence(readiness, quality, artifact, verification),
            "rights": self._rights_evidence(rights, readiness),
            "voice": self._voice_evidence(voice),
            "budget": readiness.get("budget_review") or {},
            "platform": readiness.get("platform_readiness") or {},
        }
        packet = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": org,
            "content_id": experiment.get("content_id"),
            "experiment_digest": experiment.get("experiment_digest"),
            "production_digest": production_brief.get("production_digest"),
            "artifact_digest": artifact.get("artifact_digest"),
            "verification_digest": verification.get("verification_digest"),
            "episode_package_digest": readiness.get("binding", {}).get("episode_package_digest"),
            "evidence": evidence,
            "creative": {
                "title": production_brief.get("production_brief", {}).get("title"),
                "hook": production_brief.get("production_brief", {}).get("hook"),
                "story": production_brief.get("production_brief", {}).get("story"),
                "cta": production_brief.get("production_brief", {}).get("cta"),
                "telegram_cta": production_brief.get("production_brief", {}).get("telegram_cta"),
            },
            "approval": {
                "status": "PENDING_HUMAN_APPROVAL",
                "approver_required": True,
                "approval_scope": "content_experiment_001_distribution",
                "publication_requested": False,
            },
            "execution": {
                "execution_authority": False,
                "external_publication": False,
                "auto_publish": False,
                "spend_authority": False,
            },
            "truth_boundary": {
                "local_artifact_is_proof": True,
                "platform_performance_observed": False,
                "revenue_observed": False,
                "simulation_is_not_fact": True,
            },
            "governance": {
                "read_only": True,
                "human_approval_required": True,
                "canonical_runtime": "kemet_canonical_runtime",
                "mcp": False,
            },
        }
        packet["packet_digest"] = self._digest(packet)
        return packet

    @staticmethod
    def _bind(org: int, experiment: Mapping[str, Any], brief: Mapping[str, Any], result: Mapping[str, Any]) -> None:
        if int(experiment.get("organization_id") or 0) != org:
            raise ValueError("experiment_tenant_mismatch")
        if int(brief.get("organization_id") or 0) != org or int(result.get("organization_id") or 0) != org:
            raise ValueError("production_tenant_mismatch")
        if not str(experiment.get("experiment_digest") or "").strip():
            raise ValueError("experiment_digest_required")
        if brief.get("experiment_digest") != experiment.get("experiment_digest"):
            raise ValueError("experiment_digest_mismatch")
        if not str(brief.get("production_digest") or "").strip():
            raise ValueError("production_digest_required")
        if not str((result.get("artifact") or {}).get("artifact_digest") or "").strip():
            raise ValueError("artifact_digest_required")
        if not (result.get("verification") or {}).get("verified"):
            raise ValueError("artifact_verification_required")

    @staticmethod
    def _quality_evidence(readiness: Mapping[str, Any], quality: Mapping[str, Any], artifact: Mapping[str, Any], verification: Mapping[str, Any]) -> dict[str, Any]:
        passed = [k for k, v in quality.items() if v == "PASS"]
        review = [k for k, v in quality.items() if v != "PASS"]
        return {
            "status": "REVIEW_REQUIRED" if review else "PASS",
            "quality_gates": dict(quality),
            "passed_gates": passed,
            "review_gates": review,
            "artifact_integrity": {
                "verified": bool(verification.get("verified")),
                "artifact_digest": artifact.get("artifact_digest"),
                "verification_digest": verification.get("verification_digest"),
                "checks": dict(verification.get("checks") or {}),
            },
            "readiness_digest": readiness.get("readiness_digest"),
        }

    @staticmethod
    def _rights_evidence(rights: Mapping[str, Any], readiness: Mapping[str, Any]) -> dict[str, Any]:
        checks = dict(rights.get("checks") or {})
        status = "PASS" if rights.get("status") == "PASS" and all(checks.values()) else "REVIEW_REQUIRED"
        return {
            "status": status,
            "checks": checks,
            "external_assets": list(rights.get("external_assets") or []),
            "rights_status": status,
            "historical_review": (readiness.get("historical_review") or {}).get("status"),
            "attestation_required": True,
        }

    @staticmethod
    def _voice_evidence(voice: Mapping[str, Any]) -> dict[str, Any]:
        checks = dict(voice.get("checks") or {})
        return {
            "status": "REVIEW_REQUIRED",
            "decision": voice.get("decision") or "VOICE_PROVIDER_SELECTION_REQUIRED",
            "provider_selected": bool(checks.get("provider_selected")),
            "clone_disabled": checks.get("clone_disabled") is True,
            "rights_attestation_required": checks.get("rights_attestation_required") is True,
            "evidence_reference": voice.get("evidence_reference"),
            "strategies": list(voice.get("strategies") or []),
        }

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


content_approval_packet_service = ContentApprovalPacketService()
