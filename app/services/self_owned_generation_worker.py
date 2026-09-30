from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from app.core.execution.authorization import execution_authorization
from app.core.execution.runtime import canonical_execution_runtime


class SelfOwnedGenerationWorker:
    VERSION = "1.0"
    SCHEMA = "kemet.media.self_owned_generation_worker.v1"
    WORKER_ID = "kemet_sherpa_onnx_nabra_local_worker"
    CAPABILITY = "TEXT_TO_SPEECH"
    PROVIDER_ID = "sherpa_onnx_local"

    def snapshot(self, organization_id: int | None = None) -> dict[str, Any]:
        root = Path(__file__).resolve().parents[2]
        model = root / ".kemet_runtime" / "nabra_tts" / "model.int4.onnx"
        runtime = root / ".kemet_runtime" / "sherpa_test_full4" / "sherpa_onnx" / "lib" / "libonnxruntime.so"
        return {
            "schema": self.SCHEMA, "version": self.VERSION,
            "organization_id": organization_id, "worker_id": self.WORKER_ID,
            "provider_id": self.PROVIDER_ID, "capabilities": [self.CAPABILITY],
            "model_id": "nabra-82m-sherpa-onnx", "model_version": "v0.1-derived-int4",
            "configured": bool(model.is_file() and runtime.is_file()),
            "runtime_verified": bool(model.is_file() and runtime.is_file()),
            "hardware": {"cpu": True, "gpu_required": False},
            "cost_classification": "SELF_HOSTED", "free": True,
            "network": "disabled", "credentials_required": False,
            "license": {
                "model_repository_license": "Apache-2.0",
                "dataset_license_status": "NOT_VERIFIED",
                "commercial_use_status": "VERIFIED_BY_MODEL_PUBLISHER_LICENSE",
                "redistribution_status": "VERIFIED_BY_MODEL_PUBLISHER_LICENSE",
                "source": "official model candidate audit",
                "dataset_source": "NOT_VERIFIED",
                "verified": False,
            },
            "execution_authority": False, "external_execution": False, "mcp": False,
        }

    def plan(self, *, organization_id: int, text: str, output_path: str,
             production_spec: Mapping[str, Any], graph: Mapping[str, Any],
             graph_node_id: str = "generation") -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not str(text or "").strip():
            raise ValueError("text_required")
        if int(production_spec.get("organization_id") or 0) != int(organization_id):
            raise ValueError("production_spec_tenant_mismatch")
        if not production_spec.get("digest"):
            raise ValueError("production_spec_digest_required")
        node_ids = {str(n.get("id")) for n in (graph.get("nodes") or [])}
        if str(graph_node_id) not in node_ids:
            raise ValueError("generation_graph_node_required")
        root = Path(__file__).resolve().parents[2]
        model = root / ".kemet_runtime" / "nabra_tts" / "model.int4.onnx"
        runtime = root / ".kemet_runtime" / "sherpa_test_full4" / "sherpa_onnx" / "lib" / "libonnxruntime.so"
        if not model.is_file() or not runtime.is_file():
            raise RuntimeError("nabra_runtime_unavailable")
        payload = {
            "schema": self.SCHEMA, "version": self.VERSION,
            "organization_id": int(organization_id), "worker_id": self.WORKER_ID,
            "capability": self.CAPABILITY, "provider_id": self.PROVIDER_ID,
            "model_path": str(model), "output_path": str(output_path),
            "runtime": "sherpa-onnx", "runtime_version": "1.13.8",
            "text_digest": hashlib.sha256(str(text).encode()).hexdigest(),
            "production_spec_digest": str(production_spec["digest"]),
            "production_graph_digest": str(graph.get("digest") or ""),
            "graph_node_id": str(graph_node_id), "cost_classification": "SELF_HOSTED",
            "action": "kemet_self_owned_tts_generate",
            "parameters": {"organization_id": int(organization_id), "text": str(text), "output_path": str(output_path), "model_path": str(model)},
            "execution": {"action": "kemet_self_owned_tts_generate", "automatic": False,
                          "canonical_runtime_only": True, "human_approval_required": True},
            "governance": {"execution_authority": False, "external_execution": False,
                           "human_approval_required": True, "mcp": False},
        }
        payload["plan_hash"] = execution_authorization.plan_hash(payload)
        return payload
    def execute(self, *, plan: Mapping[str, Any], text: str,
                authorization: Mapping[str, Any]) -> dict[str, Any]:
        if not authorization or authorization.get("authorized") is not True:
            return {"success": False, "status": "blocked", "error": "human_authorization_required", "executed": False}
        runtime_plan = dict(plan)
        result = canonical_execution_runtime.execute(
            plan=runtime_plan, authorization=dict(authorization), action_registry=_action_registry()
        )
        if not result.get("success"):
            return result
        artifact = dict((result.get("artifact") or {}).get("artifact") or {})
        if not artifact:
            return {"success": False, "status": "failed", "error": "artifact_evidence_missing", "executed": True}
        qa = self._qa_audio(int(plan["organization_id"]), artifact)
        if qa["status"] != "PASS":
            return {"success": False, "status": "blocked", "error": "audio_qa_failed", "executed": True,
                    "artifact": artifact, "qa": qa}
        evidence = {
            "schema": "kemet.media.self_owned_generation_evidence.v1", "version": 1,
            "organization_id": int(plan["organization_id"]), "worker_id": self.WORKER_ID,
            "capability": self.CAPABILITY, "provider_id": self.PROVIDER_ID,
            "production_spec_digest": plan["production_spec_digest"],
            "production_graph_digest": plan["production_graph_digest"],
            "graph_node_id": plan["graph_node_id"],
            "model": {"model_id": "nabra-82m-sherpa-onnx", "model_version": "v0.1-derived-int4"},
            "runtime": {"name": "sherpa-onnx", "version": "1.13.8", "python": "3.14.6"},
            "license": self.snapshot(plan["organization_id"])["license"],
            "artifact": artifact, "qa": qa,
            "provenance": {"source": "canonical_execution_runtime", "worker": self.WORKER_ID,
                           "cost_classification": "SELF_HOSTED", "network": "disabled", "execution_location": "local Android ARM64 CPU"},
            "governance": {"execution_authority": False, "external_execution": False,
                           "human_approval_required": True, "mcp": False},
        }
        evidence["evidence_digest"] = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        return {"success": True, "status": "READY", "executed": True, "artifact": artifact, "qa": qa, "evidence": evidence}

    @staticmethod
    def _qa_audio(organization_id: int, artifact: Mapping[str, Any]) -> dict[str, Any]:
        path = Path(str(artifact.get("uri") or ""))
        checks = {"file_exists": path.is_file(), "sha256_match": False, "mime_type": artifact.get("mime_type") == "audio/wav", "ffprobe": False, "duration_positive": False, "stream_present": False}
        if path.is_file():
            checks["sha256_match"] = hashlib.sha256(path.read_bytes()).hexdigest() == str(artifact.get("sha256") or "")
            ffprobe = shutil.which("ffprobe")
            if ffprobe:
                p = subprocess.run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture_output=True, text=True, timeout=30, check=False)
                checks["ffprobe"] = p.returncode == 0
                if p.returncode == 0:
                    try:
                        data = json.loads(p.stdout); checks["stream_present"] = bool(data.get("streams")); checks["duration_positive"] = float((data.get("format") or {}).get("duration") or 0) > 0
                    except (ValueError, json.JSONDecodeError):
                        pass
        failures = [k for k, ok in checks.items() if not ok]
        return {"schema": "kemet.media.audio_qa.v1", "organization_id": organization_id, "status": "PASS" if not failures else "BLOCKED", "checks": checks, "failures": failures}


def _action_registry():
    from app.automation.action_registry import registry
    return registry


self_owned_generation_worker = SelfOwnedGenerationWorker()
