from __future__ import annotations

from hashlib import sha256
import json
import shutil
from typing import Any, Mapping


class ProceduralMediaEngine:
    """Kemet-owned deterministic media generator; no remote AI provider is required."""

    VERSION = "1.0"
    MODE = "PROCEDURAL_COMPOSITED"
    CAPABILITY = "PROCEDURAL_VIDEO_GENERATION"

    def snapshot(self) -> dict[str, Any]:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        return {
            "version": self.VERSION,
            "engine": "kemet_procedural_media",
            "mode": self.MODE,
            "capability": self.CAPABILITY,
            "configured": bool(ffmpeg and ffprobe),
            "ffmpeg": ffmpeg,
            "ffprobe": ffprobe,
            "network": "disabled",
            "external_provider_required": False,
            "paid_provider_required": False,
            "personal_gpu_required": False,
            "execution_authority": False,
            "external_execution": False,
            "mcp": False,
        }

    def build_the_control_layer_plan(
        self, *, organization_id: int, output_uri: str, width: int = 1280,
        height: int = 720, fps: int = 24,
    ) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not str(output_uri or "").strip():
            raise ValueError("output_uri_required")
        if width < 640 or height < 360 or fps < 12:
            raise ValueError("invalid_video_dimensions")
        font = self._font_path()
        if not font:
            return self._blocked("font_runtime_required")
        shots = [
            (6, "FRAGMENTATION", "Information. Tools. Decisions. Everywhere."),
            (6, "ONE CONTROL LAYER", "What if your business could finally work as one?"),
            (6, "ASK  >  PLAN  >  SIMULATE", "Intent becomes an executable plan."),
            (6, "HUMAN APPROVAL", "Control stays with the people who decide."),
            (6, "GOVERNED EXECUTION", "Approved actions move through one runtime."),
            (7, "OUTCOME", "From scattered work to measurable movement."),
            (8, "KEMET AI BOS", "Don’t use another AI tool. Run your business with Kemet."),
        ]
        graph = self._build_lavfi(shots, width, height, fps, font)
        payload = {
            "schema": "kemet.procedural_media_plan.v1",
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "mode": self.MODE,
            "capability": self.CAPABILITY,
            "title": "THE CONTROL LAYER",
            "duration_seconds": sum(x[0] for x in shots),
            "shots": [
                {"shot_id": f"procedural-{i:03d}", "duration_seconds": d, "title": t,
                 "description": copy, "generation": "procedural"}
                for i, (d, t, copy) in enumerate(shots, 1)
            ],
            "source_spec": {"type": "lavfi", "value": graph},
            "output_uri": str(output_uri).strip(),
            "external_provider_required": False,
            "paid_provider_required": False,
            "personal_gpu_required": False,
            "network": "disabled",
            "governance": {
                "human_approval_required": True,
                "canonical_executor": "kemet_canonical_runtime",
                "execution_authority": False,
                "external_execution": False,
                "mcp": False,
            },
        }
        payload["digest"] = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        return {"success": True, "status": "planned", "plan": payload}

    def _build_lavfi(self, shots: list[tuple[int, str, str]], width: int, height: int, fps: int, font: str) -> str:
        """Build one deterministic lavfi stream with time-gated cinematic layers."""
        total = sum(duration for duration, _, _ in shots)
        safe_font = self._escape_drawtext(font)
        filters = [
            f"color=c=0x0b1119:s={width}x{height}:r={fps}:d={total}",
            "drawgrid=w=80:h=80:t=1:c=white@0.035",
            f"drawbox=x=0:y=0:w=2:h={height}:color=white@0.12:t=fill",
        ]
        start = 0.0
        for index, (duration, title, copy) in enumerate(shots):
            end = start + duration
            safe_title = self._escape_drawtext(title)
            safe_copy = self._escape_drawtext(copy)
            filters.append(
                f"drawbox=x={int(width*0.10)}:y={int(height*0.22)}:w={int(width*0.80)}:h={int(height*0.52)}:color=0x17212d@0.70:t=fill:"
                f"enable='between(t,{start:.3f},{end:.3f})'"
            )
            filters.append(
                f"drawtext=fontfile='{safe_font}':text='{safe_title}':fontcolor=white:fontsize=58:"
                f"x='(w-text_w)/2+18*sin(t*1.1)':y=h*0.38:"
                f"enable='between(t,{start:.3f},{end:.3f})'"
            )
            filters.append(
                f"drawtext=fontfile='{safe_font}':text='{safe_copy}':fontcolor=white@0.78:fontsize=28:"
                f"x='(w-text_w)/2':y=h*0.52:"
                f"enable='between(t,{start:.3f},{end:.3f})'"
            )
            start = end
        filters.append("format=yuv420p")
        return ",".join(filters)

    @staticmethod
    def _escape_drawtext(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    @staticmethod
    def _font_path() -> str | None:
        candidates = (
            "/system/fonts/Roboto-Regular.ttf",
            "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
        for path in candidates:
            if __import__("os").path.isfile(path):
                return path
        return None

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": "blocked",
            "error": error,
            "external_provider_required": False,
            "paid_provider_required": False,
            "personal_gpu_required": False,
            "execution_authority": False,
            "external_execution": False,
            "mcp": False,
        }


procedural_media_engine = ProceduralMediaEngine()
