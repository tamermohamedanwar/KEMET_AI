from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
import shutil
from typing import Any


@dataclass(frozen=True)
class PiperProvider:
    provider_id: str = "piper_local"
    executable_env: str = "KEMET_PIPER_EXECUTABLE"
    language: str = "ar_JO"
    network_mode: str = "disabled_by_default"
    cost_model: str = "local_no_api_fee"


class PiperTTSService:
    VERSION = "1.0"
    SCHEMA = "kemet.voice.piper_local.v1"
    provider = PiperProvider()

    def snapshot(self, organization_id: int | None) -> dict[str, Any]:
        executable = self._executable()
        return {
            "version": self.VERSION,
            "schema": self.SCHEMA,
            "organization_id": organization_id,
            "provider_id": self.provider.provider_id,
            "language": self.provider.language,
            "configured": bool(executable),
            "executable": executable,
            "cost_model": self.provider.cost_model,
            "network": self.provider.network_mode,
            "credentials_required": False,
            "execution_authority": False,
            "human_approval_required": True,
        }

    def plan(self, *, organization_id: int, text: str, output_path: str) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            return self._blocked("organization_required")
        if not str(text or "").strip():
            return self._blocked("text_required")
        if not str(output_path or "").strip():
            return self._blocked("output_path_required")
        executable = self._executable()
        if not executable:
            return self._blocked("piper_executable_not_configured")
        payload = {
            "version": self.VERSION,
            "schema": self.SCHEMA,
            "organization_id": org,
            "provider_id": self.provider.provider_id,
            "language": self.provider.language,
            "output_path": str(output_path).strip(),
            "text_digest": sha256(str(text).encode("utf-8")).hexdigest(),
            "cost_model": self.provider.cost_model,
            "credentials_required": False,
            "network": self.provider.network_mode,
            "execution": {"automatic": False, "canonical_runtime_only": True},
            "governance": {
                "execution_authority": False,
                "human_approval_required": True,
                "external_execution": False,
            },
        }
        payload["plan_digest"] = sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {"success": True, "status": "planned", "plan": payload}

    def _executable(self) -> str | None:
        configured = os.getenv(self.provider.executable_env, "").strip()
        if configured and os.path.isfile(configured) and os.access(configured, os.X_OK):
            return configured
        discovered = shutil.which("piper")
        return discovered

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": "blocked",
            "error": error,
            "provider_id": "piper_local",
            "credentials_required": False,
            "execution_authority": False,
        }


piper_tts_service = PiperTTSService()
