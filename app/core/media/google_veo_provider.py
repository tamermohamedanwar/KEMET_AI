from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import base64
import mimetypes
import time
from typing import Any, Mapping

import requests


class GoogleVeoProvider:
    PROVIDER_ID = "google_veo_3_1"
    MODEL = "veo-3.1-generate-preview"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    VERSION = "1.0"

    def preflight(self) -> dict[str, Any]:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return {
            "provider_id": self.PROVIDER_ID,
            "model": self.MODEL,
            "configured": bool(key),
            "credential_env": "GEMINI_API_KEY" if os.getenv("GEMINI_API_KEY") else "GOOGLE_API_KEY" if os.getenv("GOOGLE_API_KEY") else None,
            "network": "disabled_until_approval",
            "execution_authority": False,
            "external_execution": False,
            "mcp": False,
        }

    def generate_shot(
        self,
        *,
        organization_id: int,
        episode_id: str,
        shot: Mapping[str, Any],
        approval: Mapping[str, Any],
        output_path: str,
        timeout_seconds: int = 900,
    ) -> dict[str, Any]:
        self._approved(organization_id, shot, approval)
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            return self._blocked("provider_credential_missing")
        shot_digest = self._shot_digest(shot)
        prompt = str(shot.get("provider_prompt") or "").strip()
        if not prompt:
            return self._blocked("derived_provider_prompt_required")
        duration = str(int(float(shot.get("duration_seconds") or 8)))
        if duration not in {"4", "6", "8"}:
            duration = "8"
        body = {"instances": [{"prompt": prompt}], "parameters": {"aspectRatio": "16:9", "resolution": "720p", "durationSeconds": duration}}
        reference_images = self._reference_images(shot.get("reference_images") or [])
        if reference_images:
            if duration != "8":
                return self._blocked("reference_images_require_8_seconds")
            body["instances"][0]["referenceImages"] = reference_images[:3]
        headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
        url = f"{self.BASE_URL}/models/{self.MODEL}:predictLongRunning"
        response = requests.post(url, headers=headers, json=body, timeout=60)
        if response.status_code >= 400:
            return self._blocked(f"provider_http_{response.status_code}", response.text[-500:])
        operation = response.json()
        name = str(operation.get("name") or "").strip()
        if not name:
            return self._blocked("provider_operation_missing")
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            status = requests.get(f"{self.BASE_URL}/{name}", headers={"x-goog-api-key": key}, timeout=60)
            if status.status_code >= 400:
                return self._blocked(f"provider_poll_http_{status.status_code}", status.text[-500:])
            payload = status.json()
            if payload.get("error"):
                return self._blocked("provider_operation_failed", json.dumps(payload["error"], default=str)[-500:])
            if payload.get("done") is True:
                uri = (((payload.get("response") or {}).get("generateVideoResponse") or {}).get("generatedSamples") or [{}])[0].get("video", {}).get("uri")
                if not uri:
                    return self._blocked("provider_video_uri_missing")
                target = Path(output_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                download = requests.get(uri, headers={"x-goog-api-key": key}, timeout=120)
                if download.status_code >= 400:
                    return self._blocked(f"provider_download_http_{download.status_code}", download.text[-500:])
                target.write_bytes(download.content)
                digest = self._file_digest(target)
                return {
                    "success": True,
                    "status": "generated",
                    "provider_id": self.PROVIDER_ID,
                    "model": self.MODEL,
                    "episode_id": episode_id,
                    "shot_id": str(shot.get("shot_id")),
                    "canonical_shot_digest": shot_digest,
                    "artifact_digest": digest,
                    "artifact_uri": str(target),
                    "trust": "untrusted",
                    "execution_authority": False,
                    "external_execution": True,
                    "mcp": False,
                }
            time.sleep(10)
        return self._blocked("provider_operation_timeout")

    @staticmethod
    def _reference_images(references: list[Any]) -> list[dict[str, Any]]:
        result = []
        for reference in references[:3]:
            if not isinstance(reference, Mapping):
                continue
            path = str(reference.get("path") or "").strip()
            if not path or not Path(path).is_file():
                continue
            mime = str(reference.get("mime_type") or mimetypes.guess_type(path)[0] or "image/png")
            data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
            result.append({
                "referenceType": str(reference.get("reference_type") or "asset"),
                "image": {
                    "bytesBase64Encoded": data,
                    "mimeType": mime,
                },
            })
        return result

    @staticmethod
    def _approved(organization_id: int, shot: Mapping[str, Any], approval: Mapping[str, Any]) -> None:
        if organization_id <= 0:
            raise ValueError("organization_required")
        if not shot.get("shot_id") or not shot.get("canonical_shot_digest"):
            raise ValueError("canonical_shot_binding_required")
        if approval.get("approved") is not True:
            raise ValueError("human_approval_required")
        if approval.get("organization_id") != organization_id:
            raise ValueError("approval_tenant_mismatch")
        if approval.get("shot_id") != shot.get("shot_id"):
            raise ValueError("approval_shot_mismatch")
        if approval.get("canonical_shot_digest") != shot.get("canonical_shot_digest"):
            raise ValueError("approval_shot_digest_mismatch")

    @staticmethod
    def _shot_digest(shot: Mapping[str, Any]) -> str:
        return str(shot["canonical_shot_digest"])

    @staticmethod
    def _file_digest(path: Path) -> str:
        h = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _blocked(error: str, detail: str | None = None) -> dict[str, Any]:
        result = {"success": False, "status": "blocked", "error": error, "execution_authority": False, "mcp": False}
        if detail:
            result["detail"] = detail
        return result


google_veo_provider = GoogleVeoProvider()
