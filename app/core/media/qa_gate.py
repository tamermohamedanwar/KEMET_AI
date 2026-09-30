from __future__ import annotations
from hashlib import sha256
import json, shutil, subprocess
from pathlib import Path
from typing import Any, Mapping
from app.core.media.artifacts import artifact_metadata
from app.core.media.contracts import QA_PLAN, build_contract, contract_digest
from app.core.media.governance import governance_envelope

class MediaQAGateV1:
    VERSION = "1.0"

    @staticmethod
    def _digest(value: Any) -> str:
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    @staticmethod
    def _file_digest(path: Path) -> str:
        h = sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def snapshot(self) -> dict[str, Any]:
        return {"version": self.VERSION, "ffprobe": shutil.which("ffprobe"),
                "execution_authority": False, "external_execution": False,
                "network": "disabled", "mcp": False}

    def inspect(self, *, organization_id: int, artifact: Mapping[str, Any],
                expected_mime: str = "video/mp4") -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        if not isinstance(artifact, Mapping):
            raise ValueError("artifact_required")
        if int(artifact.get("organization_id") or 0) != int(organization_id):
            raise ValueError("artifact_tenant_mismatch")
        uri = str(artifact.get("uri") or "")
        if not uri or "://" in uri and not uri.startswith("file://"):
            return self._blocked(organization_id, "local_artifact_required")
        path = Path(uri.removeprefix("file://"))
        if not path.is_file():
            return self._blocked(organization_id, "artifact_missing")
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return self._blocked(organization_id, "ffprobe_runtime_required")
        digest = self._file_digest(path)
        digest_match = digest == str(artifact.get("digest") or "")
        mime = str(artifact.get("mime_type") or "")
        checks = {"file_exists": True, "sha256_match": digest_match,
                  "mime_type": mime == expected_mime, "ffprobe": False,
                  "duration_positive": False, "stream_present": False}
        probe = self._probe(ffprobe, path)
        checks["ffprobe"] = probe is not None
        streams = (probe or {}).get("streams") or []
        checks["stream_present"] = bool(streams)
        fmt = (probe or {}).get("format") or {}
        try: checks["duration_positive"] = float(fmt.get("duration") or 0) > 0
        except (TypeError, ValueError): checks["duration_positive"] = False
        failures = [name for name, ok in checks.items() if not ok]
        status = "PASS" if not failures else "BLOCKED"
        payload = {"schema": QA_PLAN, "version": self.VERSION, "organization_id": int(organization_id),
                   "artifact_id": artifact.get("artifact_id"), "artifact_digest": digest,
                   "checks": checks, "failures": failures, "status": status,
                   "governance": {**governance_envelope(organization_id=int(organization_id), action="media.qa"),
                                  "execution_authority": False, "external_execution": False,
                                  "auto_publish": False, "mcp": False}}
        contract = build_contract(QA_PLAN, organization_id=int(organization_id),
                                  payload=payload, contract_id=self._digest(payload)[:32])
        contract.update(payload)
        contract["digest"] = contract_digest({k: v for k, v in contract.items() if k != "digest"})
        contract["contract_digest"] = contract["digest"]
        contract["probe"] = probe or {}
        contract["execution_authority"] = False
        contract["external_execution"] = False
        contract["mcp"] = False
        contract["artifact"] = artifact_metadata(artifact_id=str(artifact.get("artifact_id")),
            organization_id=int(organization_id), kind="video", mime_type=mime or expected_mime,
            digest=digest, uri=str(path))
        return contract

    @staticmethod
    def _probe(ffprobe: str, path: Path) -> dict[str, Any] | None:
        try:
            result = subprocess.run([ffprobe, "-v", "error", "-show_format", "-show_streams",
                                     "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return None
        if result.returncode != 0:
            return None
        try: return json.loads(result.stdout)
        except json.JSONDecodeError: return None

    @staticmethod
    def _blocked(organization_id: int, error: str) -> dict[str, Any]:
        return {"schema": QA_PLAN, "version": MediaQAGateV1.VERSION,
                "organization_id": int(organization_id), "status": "BLOCKED",
                "error": error, "execution_authority": False, "external_execution": False,
                "auto_publish": False, "mcp": False}

media_qa_gate_v1 = MediaQAGateV1()
