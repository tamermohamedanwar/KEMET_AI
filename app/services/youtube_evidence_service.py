from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.core.evidence import execution_evidence_fabric
from app.services.google_visibility_measurement_service import build_youtube_evidence


class YouTubeEvidenceService:
    VERSION = "1.0"

    @staticmethod
    def _worker_path() -> Path:
        return Path(__file__).resolve().parents[2] / "ops" / "youtube_worker" / "analytics.mjs"

    def measure(self, organization_id: int) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_required")
        worker = self._worker_path()
        if not worker.exists():
            raise ValueError("youtube_measurement_worker_missing")
        completed = subprocess.run(
            ["node", str(worker)],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        payload = json.loads(lines[-1]) if lines else {}
        if completed.returncode != 0 or payload.get("verified_source") is not True:
            raise ValueError(payload.get("message") or payload.get("error") or "youtube_measurement_failed")
        measurement = build_youtube_evidence(organization_id, payload)
        digest_payload = {"version": self.VERSION, "measurement": measurement}
        digest = execution_evidence_fabric.digest(digest_payload)
        return {**measurement, "evidence_digest": digest, "evidence_contract": "Kemet Evidence Fabric"}


youtube_evidence_service = YouTubeEvidenceService()
