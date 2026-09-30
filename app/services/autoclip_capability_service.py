from __future__ import annotations

from hashlib import sha256
import json
import os
import platform
import shutil
from typing import Any

class AutoClipCapabilityService:
    VERSION = "1.0"
    CAPABILITY_ID = "autoclip_local_shortform"
    SOURCE_REPOSITORY = "https://github.com/artbyjazi/autoclip"
    LICENSE = "MIT"
    SUPPORTED_PYTHON = ("3.11", "3.12")
    STAGES = ("ingest", "prepare", "transcribe", "highlights", "reframe", "captions", "export")

    def snapshot(self, organization_id: int | None = None) -> dict[str, Any]:
        executable = self._executable()
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        return {
            "version": self.VERSION,
            "capability_id": self.CAPABILITY_ID,
            "organization_id": organization_id,
            "provider": "autoclip_local",
            "source_repository": self.SOURCE_REPOSITORY,
            "license": self.LICENSE,
            "configured": bool(executable),
            "executable": executable,
            "ffmpeg_available": bool(ffmpeg),
            "ffprobe_available": bool(ffprobe),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "stages": list(self.STAGES),
            "execution_authority": False,
            "governance": self._governance(),
        }

    def plan(self, *, organization_id: int, input_uri: str,
             language: str = "ar", clip_count: int = 5,
             aspect_ratio: str = "9:16") -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            return self._blocked("organization_required")
        if not str(input_uri or "").strip():
            return self._blocked("input_uri_required")
        if clip_count < 1 or clip_count > 50:
            return self._blocked("clip_count_out_of_range")
        if aspect_ratio not in {"9:16", "1:1", "16:9"}:
            return self._blocked("unsupported_aspect_ratio")

        executable = self._executable()
        payload = {
            "schema": "kemet.autoclip_plan.v1",
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "provider_id": "autoclip_local",
            "input_uri": str(input_uri).strip(),
            "language": str(language or "ar").strip(),
            "clip_count": int(clip_count),
            "aspect_ratio": aspect_ratio,
            "stages": list(self.STAGES),
            "runtime": {
                "configured": bool(executable),
                "executable": executable,
                "ffmpeg_available": bool(shutil.which("ffmpeg")),
                "ffprobe_available": bool(shutil.which("ffprobe")),
                "network": "disabled_by_default",
            },
            "execution": {
                "automatic": False,
                "canonical_runtime_only": True,
                "publication": False,
            },
            "governance": self._governance(),
        }
        payload["plan_digest"] = sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        if not executable:
            return {"success": False, "status": "runtime_probe_required", "plan": payload}
        return {"success": True, "status": "planned", "plan": payload}

    @staticmethod
    def _executable() -> str | None:
        configured = os.getenv("KEMET_AUTOCLIP_EXECUTABLE", "").strip()
        return configured or shutil.which("autoclip")

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "advisory": True,
            "untrusted_infrastructure": True,
            "execution_authority": False,
            "external_execution": False,
            "auto_publish": False,
            "human_approval_required": True,
            "canonical_executor": "kemet_canonical_runtime",
            "rights_review_required": True,
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

autoclip_capability_service = AutoClipCapabilityService()
