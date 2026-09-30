from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.services.local_media_provider_service import local_media_provider_service


class MendesScriptVoiceContractService:
    VERSION = "1.0"

    def build(self, *, organization_id: int, episode_package: Mapping[str, Any],
              approved_script: Mapping[str, Any], voice_profile: Mapping[str, Any],
              voice_rights_attestation: str | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            return self._blocked("organization_required")
        if not episode_package or episode_package.get("organization_id") != int(organization_id):
            return self._blocked("episode_package_tenant_mismatch")
        if episode_package.get("approval_status") not in {"approved", "approval_granted"}:
            return self._blocked("script_approval_required")
        if not str(approved_script.get("script_digest") or "").strip():
            return self._blocked("script_digest_required")
        if not str(approved_script.get("text") or "").strip():
            return self._blocked("approved_script_text_required")
        if not str(voice_profile.get("voice_id") or "").strip():
            return self._blocked("voice_profile_required")

        capability = "voice_clone" if voice_profile.get("mode") == "clone" else "tts"
        voice_plan = local_media_provider_service.plan(
            organization_id=int(organization_id),
            capability=capability,
            input_uri=f"script:{approved_script['script_digest']}",
            output_format=str(voice_profile.get("output_format") or "wav"),
            language=str(voice_profile.get("language") or "ar-EG"),
            voice_rights_attestation=voice_rights_attestation,
        )
        if not voice_plan.get("success"):
            return self._blocked(voice_plan.get("error", "voice_plan_blocked"))

        payload = {
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "episode_package_digest": episode_package.get("package_digest"),
            "script_digest": approved_script["script_digest"],
            "voice_profile": {
                "voice_id": str(voice_profile["voice_id"]),
                "mode": capability,
                "language": str(voice_profile.get("language") or "ar-EG"),
            },
            "voice_plan": voice_plan["plan"],
            "rights": {
                "attestation_present": bool(voice_rights_attestation),
                "required_for_clone": capability == "voice_clone",
            },
            "status": "planned",
            "governance": {
                "execution_authority": False,
                "external_execution": False,
                "human_approval_required": True,
                "canonical_runtime": "kemet_canonical_runtime",
            },
        }
        payload["contract_digest"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        return {"success": True, "status": "planned", "contract": payload}

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "error": error,
                "execution_authority": False, "human_approval_required": True}


mendes_script_voice_contract_service = MendesScriptVoiceContractService()
