from __future__ import annotations

from hashlib import sha256
import json
import os
import shutil
import subprocess
from typing import Any


class NativeShortformService:
    VERSION = "1.1"
    CAPABILITY_ID = "kemet_native_shortform"
    STAGES = ("probe", "candidate_selection", "reframe", "captions", "render", "review")

    def snapshot(self, organization_id: int | None = None) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "capability_id": self.CAPABILITY_ID,
            "organization_id": organization_id,
            "provider": "kemet_native_ffmpeg",
            "configured": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
            "ffmpeg": shutil.which("ffmpeg"),
            "ffprobe": shutil.which("ffprobe"),
            "network": "disabled",
            "execution_authority": False,
            "governance": self._governance(),
        }

    def plan(self, *, organization_id: int, input_uri: str, clip_count: int = 5,
             aspect_ratio: str = "9:16", language: str = "ar",
             transcript: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            return self._blocked("organization_required")
        path = str(input_uri or "").strip()
        if not path:
            return self._blocked("input_uri_required")
        if path.startswith(("http://", "https://", "rtmp://", "s3://", "gs://")):
            return self._blocked("local_input_required")
        if clip_count < 1 or clip_count > 50:
            return self._blocked("clip_count_out_of_range")
        if aspect_ratio not in {"9:16", "1:1", "16:9"}:
            return self._blocked("unsupported_aspect_ratio")
        if not os.path.isfile(path):
            return {"success": False, "status": "input_not_found", "error": "input_not_found",
                    "capability_id": self.CAPABILITY_ID, "governance": self._governance()}
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            return {"success": False, "status": "runtime_probe_required", "error": "ffmpeg_runtime_required",
                    "capability_id": self.CAPABILITY_ID, "governance": self._governance()}
        probe = self._probe(path)
        duration = float(probe.get("duration") or 0)
        candidates = self._candidates(duration, clip_count, transcript or [])
        payload = {
            "schema": "kemet.native_shortform_plan.v1",
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "capability_id": self.CAPABILITY_ID,
            "input": {"path": os.path.abspath(path), "probe": probe},
            "language": str(language or "ar"),
            "transcript": {"provided": bool(transcript), "segments": len(transcript or [])},
            "aspect_ratio": aspect_ratio,
            "stages": list(self.STAGES),
            "candidates": candidates,
            "execution": {"automatic": False, "approved_only": True, "publication": False},
            "governance": self._governance(),
        }
        payload["plan_digest"] = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        return {"success": True, "status": "planned", "plan": payload}

    @staticmethod
    def _probe(path: str) -> dict[str, Any]:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,format_name", "-of", "json", path],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if result.returncode != 0:
            return {"valid": False, "error": "ffprobe_failed"}
        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            return {"valid": False, "error": "ffprobe_invalid_json"}
        fmt = data.get("format") or {}
        return {"valid": True, "duration": float(fmt.get("duration") or 0), "format_name": fmt.get("format_name")}

    @staticmethod
    def _candidates(duration: float, count: int, transcript: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if duration <= 0:
            return []
        window = min(45.0, max(12.0, duration / max(count, 1)))
        if duration <= window:
            return [{"index": 1, "start": 0.0, "duration": round(duration, 3), "selection": "full_asset"}]
        max_start = max(0.0, duration - window)
        if transcript:
            scored = []
            for segment in transcript:
                try:
                    start = max(0.0, float(segment.get("start", 0)))
                    end = min(duration, float(segment.get("end", start)))
                except (TypeError, ValueError):
                    continue
                text = str(segment.get("text", "")).strip()
                if not text or end <= start:
                    continue
                center = min(max(0.0, start), max_start)
                score = min(len(text), 240) / 240.0
                scored.append((score, center))
            if scored:
                selected = []
                for score, center in sorted(scored, key=lambda item: (-item[0], item[1])):
                    start = min(max_start, max(0.0, center - window / 2.0))
                    candidate = {"index": len(selected) + 1, "start": round(start, 3),
                                 "duration": round(window, 3), "selection": "transcript_scored",
                                 "score": round(score, 4)}
                    if all(abs(candidate["start"] - item["start"]) >= window * 0.5 for item in selected):
                        selected.append(candidate)
                    if len(selected) >= count:
                        return selected
                if selected:
                    return selected
        step = max_start / max(count - 1, 1)
        return [
            {"index": i + 1, "start": round(i * step, 3), "duration": round(window, 3), "selection": "deterministic_candidate"}
            for i in range(count)
        ]

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"mode": "advisory", "execution_authority": False, "external_execution": False,
                "network": "disabled", "human_approval_required": True,
                "canonical_executor": "kemet_canonical_runtime", "auto_publish": False}

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "error": error,
                "capability_id": NativeShortformService.CAPABILITY_ID,
                "execution_authority": False, "governance": NativeShortformService._governance()}


native_shortform_service = NativeShortformService()
