from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
import shutil
from typing import Any


@dataclass(frozen=True)
class LocalMediaProvider:
    provider_id: str
    name: str
    executable_env: str
    capabilities: tuple[str, ...]
    provenance: str
    license_class: str
    max_runtime_seconds: int = 900
    executable_name: str | None = None


class LocalMediaProviderService:
    VERSION = "1.1"
    CAPABILITIES = (
        "tts", "voice_clone", "dubbing", "stt", "speaker_separation",
        "denoise", "music", "sfx",
    )
    PROVIDERS = (
        LocalMediaProvider(
            "piper_local", "Piper local TTS", "KEMET_PIPER_EXECUTABLE",
            ("tts",), "local_open_source_runtime",
            "model_and_dataset_license_review_required",
            executable_name="piper",
        ),
        LocalMediaProvider(
            "voder", "VODER local media engine", "KEMET_VODER_EXECUTABLE",
            CAPABILITIES, "external_local_tool", "external_license_review_required",
        ),
    )

    def snapshot(self, organization_id: int | None) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "organization_id": organization_id,
            "providers": [self._provider_snapshot(p) for p in self.PROVIDERS],
            "governance": self._governance(),
        }

    def plan(self, *, organization_id: int, capability: str, input_uri: str,
             output_format: str, language: str = "ar-EG",
             voice_rights_attestation: str | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            return self._blocked("organization_required")
        if capability not in self.CAPABILITIES:
            return self._blocked("unsupported_media_capability")
        if not str(input_uri or "").strip():
            return self._blocked("input_uri_required")
        if not str(output_format or "").strip():
            return self._blocked("output_format_required")
        if capability == "voice_clone" and not str(voice_rights_attestation or "").strip():
            return self._blocked("voice_rights_attestation_required")
        providers = [p for p in self.PROVIDERS if capability in p.capabilities]
        if not providers:
            return self._blocked("no_provider_for_capability")
        provider = providers[0]
        executable = self._resolve_executable(provider)
        payload = {
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "capability": capability,
            "provider_id": provider.provider_id,
            "input_uri": str(input_uri).strip(),
            "output_format": str(output_format).strip().lower(),
            "language": str(language or "ar-EG").strip(),
            "provider_configured": bool(executable),
            "provider_executable": executable,
            "voice_rights": {"required": capability == "voice_clone", "attested": bool(voice_rights_attestation)},
            "resource_limits": {"max_runtime_seconds": provider.max_runtime_seconds, "network": "disabled_by_default"},
            "execution": {"automatic": False, "canonical_runtime_only": True},
            "governance": self._governance(),
        }
        payload["plan_digest"] = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        return {"success": True, "status": "planned", "plan": payload}

    @staticmethod
    def _resolve_executable(provider: LocalMediaProvider) -> str | None:
        configured = os.getenv(provider.executable_env, "").strip()
        if configured and os.path.isfile(configured) and os.access(configured, os.X_OK):
            return configured
        if provider.executable_name:
            return shutil.which(provider.executable_name)
        return None

    @classmethod
    def _provider_snapshot(cls, provider: LocalMediaProvider) -> dict[str, Any]:
        return {
            "provider_id": provider.provider_id,
            "name": provider.name,
            "capabilities": list(provider.capabilities),
            "provenance": provider.provenance,
            "license_class": provider.license_class,
            "configured": bool(cls._resolve_executable(provider)),
            "credentials_exposed": False,
            "execution_authority": False,
        }

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "advisory": True,
            "untrusted_infrastructure": True,
            "execution_authority": False,
            "external_execution": False,
            "database_mutation": False,
            "human_approval_required": True,
            "canonical_executor": "kemet_canonical_runtime",
            "license_review_required": True,
            "rights_review_required_for_voice_clone": True,
        }

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": "blocked",
            "error": error,
            "execution_authority": False,
            "credentials_exposed": False,
        }


local_media_provider_service = LocalMediaProviderService()
