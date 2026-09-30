from __future__ import annotations

from typing import Any, Mapping
import hashlib
import json


class VoiceProviderDecisionService:
    VERSION = "1.0"
    SCHEMA = "kemet.voice.provider_decision.v1"

    def build(self, *, organization_id: int, readiness: Mapping[str, Any]) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            return self._blocked("organization_required")
        voice = dict(readiness.get("voice_review") or {})
        evidence = dict(voice.get("evidence") or {})
        candidate = {
            "provider": voice.get("candidate_provider") or "voder",
            "commercial_use_status": evidence.get("commercial_use"),
            "pricing_source": evidence.get("pricing_uri"),
            "terms_source": evidence.get("terms_uri"),
            "service_terms_source": evidence.get("service_terms_uri"),
            "retrieved_at": evidence.get("retrieved_at") or "2026-09-18",
            "voice_clone": False,
            "rights_attestation_required": True,
        }
        candidate["evidence_digest"] = self._digest(candidate)
        free_local_candidate = {
            "provider": "voder",
            "cost_model": "local_compute",
            "credentials_required": False,
            "network": "disabled_by_default",
            "language": "ar_JO",
            "selection_requires_runtime_probe": True,
            "execution_authority": False,
        }
        free_local_candidate["evidence_digest"] = self._digest(free_local_candidate)
        strategies = voice.get("strategies") or []
        return {
            "success": True,
            "status": "DECISION_REQUIRED",
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": org,
            "decision": "VODER_LOCAL_CANDIDATE",
            "selected": False,
            "selected_provider": None,
            "candidate": candidate,
            "free_local_candidate": free_local_candidate,
            "strategies": strategies,
            "decision_contract": {
                "allowed_values": ["voder_local_candidate", "human_voice", "other_verified_provider"],
                "selection_must_be_explicit": True,
                "selection_does_not_grant_execution_authority": True,
                "voice_clone_default": False,
                "rights_attestation_required": True,
            },
            "governance": {
                "read_only": True,
                "human_decision_required": True,
                "execution_authority": False,
                "credentials_exposed": False,
                "mcp": False,
            },
            "truth_boundary": "Candidate evidence is not provider selection, purchase, authorization, or execution.",
        }

    @staticmethod
    def _digest(value: Mapping[str, Any]) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": "BLOCKED",
            "error": error,
            "governance": {"read_only": True, "execution_authority": False, "credentials_exposed": False, "mcp": False},
        }


voice_provider_decision_service = VoiceProviderDecisionService()
