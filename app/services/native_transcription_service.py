from __future__ import annotations

from hashlib import sha256
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from typing import Any

from app.core.runtime.model_artifact import is_valid_model, model_path
from app.core.runtime.resource_guard import choose_model, decide


class NativeTranscriptionService:
    VERSION = "1.1"
    CAPABILITY_ID = "kemet_native_transcription"

    def snapshot(self, organization_id: int | None = None) -> dict[str, Any]:
        executable = self._executable()
        selected_model, model, decision = self._resolve_model()
        model_valid = bool(model and selected_model and is_valid_model(model, selected_model))
        return {
            "version": self.VERSION,
            "capability_id": self.CAPABILITY_ID,
            "organization_id": organization_id,
            "provider": "whisper_cpp_local",
            "configured": bool(executable and model_valid and decision.get("allowed")),
            "executable": executable,
            "model_path": model or None,
            "model": selected_model or None,
            "model_valid": model_valid,
            "resource_decision": decision,
            "ffmpeg": shutil.which("ffmpeg"),
            "network": "disabled",
            "execution_authority": False,
            "governance": self._governance(),
        }

    def transcribe(self, *, organization_id: int, input_uri: str,
                   language: str = "ar") -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            return self._blocked("organization_required")
        path = str(input_uri or "").strip()
        if not path:
            return self._blocked("input_uri_required")
        if path.startswith(("http://", "https://", "rtmp://", "s3://", "gs://")):
            return self._blocked("local_input_required")
        if not os.path.isfile(path):
            return self._blocked("input_not_found")
        executable = self._executable()
        selected_model, model, decision = self._resolve_model()
        if not executable or not os.path.isfile(executable):
            return {"success": False, "status": "runtime_probe_required", "error": "whisper_runtime_required", "governance": self._governance()}
        if not selected_model:
            return {"success": False, "status": "resource_blocked", "error": "whisper_insufficient_memory", "governance": self._governance()}
        if not decision.get("allowed"):
            return {"success": False, "status": "resource_blocked", "error": "whisper_insufficient_memory", "resource_decision": decision, "governance": self._governance()}
        if not model or not is_valid_model(model, selected_model):
            return {"success": False, "status": "model_required", "error": "whisper_model_unavailable", "model": selected_model, "governance": self._governance()}
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return {"success": False, "status": "runtime_probe_required", "error": "ffmpeg_runtime_required", "governance": self._governance()}
        with tempfile.TemporaryDirectory(prefix="kemet_whisper_") as tmp:
            wav = os.path.join(tmp, "audio.wav")
            convert = subprocess.run([ffmpeg, "-y", "-i", path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav], capture_output=True, text=True, check=False, timeout=120)
            if convert.returncode != 0:
                return {"success": False, "status": "conversion_failed", "error": "audio_conversion_failed", "governance": self._governance()}
            result = subprocess.run([executable, "-m", model, "-f", wav, "-l", str(language or "ar"), "--output-json", "--no-prints"], capture_output=True, text=True, check=False, timeout=int(os.getenv("KEMET_WHISPER_TIMEOUT_SECONDS", "600")))
            if result.returncode != 0:
                return {"success": False, "status": "transcription_failed", "error": "whisper_failed", "stderr": result.stderr[-2000:], "governance": self._governance()}
            json_path = f"{wav}.json"
            json_output = result.stdout
            if os.path.isfile(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as fh:
                        json_output = fh.read()
                except OSError:
                    pass
            parsed = self._parse_json_output(json_output)
        digest = sha256(json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"success": True, "status": "transcribed", "transcript": parsed, "transcript_digest": digest, "governance": self._governance()}

    @staticmethod
    def _parse_json_output(stdout: str) -> list[dict[str, Any]]:
        try:
            data = json.loads(stdout or "{}")
        except json.JSONDecodeError:
            return []
        segments = data.get("transcription") or data.get("segments") or []
        return [
            {"start": float(item.get("offsets", {}).get("from", item.get("start", 0))) / 1000.0,
             "end": float(item.get("offsets", {}).get("to", item.get("end", 0))) / 1000.0,
             "text": str(item.get("text", "")).strip()}
            for item in segments if str(item.get("text", "")).strip()
        ]

    @staticmethod
    def _resolve_model() -> tuple[str | None, str, dict[str, Any]]:
        preferred_model = os.getenv("KEMET_WHISPER_MODEL", "").strip().lower()
        configured_path = os.getenv("KEMET_WHISPER_MODEL_PATH", "").strip()
        selected_model = preferred_model or choose_model()
        model = configured_path or (str(model_path(selected_model)) if selected_model else "")
        decision = asdict(decide(selected_model)) if selected_model else {"allowed": False, "reason": "no_model_fits"}

        if not preferred_model and not configured_path and selected_model and not is_valid_model(model, selected_model):
            fallback = "tiny"
            fallback_path = str(model_path(fallback))
            fallback_decision = asdict(decide(fallback))
            if fallback_decision.get("allowed") and is_valid_model(fallback_path, fallback):
                return fallback, fallback_path, fallback_decision

        return selected_model, model, decision

    @staticmethod
    def _executable() -> str | None:
        configured = os.getenv("KEMET_WHISPER_CPP_EXECUTABLE", "").strip()
        candidates = [configured, os.path.expanduser("~/products/Kemet_AI/.kemet_runtime/whisper_cpp/build/bin/whisper-cli"), os.path.expanduser("~/products/Kemet_AI/.kemet_runtime/whisper_cpp/bin/whisper-cli"), shutil.which("whisper-cli")]
        return next((item for item in candidates if item and os.path.isfile(item) and os.access(item, os.X_OK)), None)

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"advisory": True, "execution_authority": False, "external_execution": False, "network": "disabled", "human_approval_required": True, "canonical_executor": "kemet_canonical_runtime", "auto_publish": False}

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "error": error, "execution_authority": False, "governance": NativeTranscriptionService._governance()}


native_transcription_service = NativeTranscriptionService()
