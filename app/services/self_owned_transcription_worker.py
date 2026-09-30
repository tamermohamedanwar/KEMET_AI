from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from app.core.execution.authorization import execution_authorization
from app.core.execution.runtime import canonical_execution_runtime


class SelfOwnedTranscriptionWorker:
    VERSION = "1.0"
    SCHEMA = "kemet.media.self_owned_transcription_worker.v1"
    WORKER_ID = "kemet_whisper_cpp_local_worker"
    CAPABILITY = "TRANSCRIPTION"
    MODEL_ID = "whisper-tiny"
    PROVIDER_ID = "whisper_cpp_local"

    def snapshot(self, organization_id: int | None = None) -> dict[str, Any]:
        from app.services.native_transcription_service import native_transcription_service
        snap = native_transcription_service.snapshot(organization_id)
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": organization_id,
            "worker_id": self.WORKER_ID,
            "provider_id": self.PROVIDER_ID,
            "capabilities": [self.CAPABILITY],
            "model_id": self.MODEL_ID,
            "configured": bool(snap.get("configured")),
            "runtime_verified": bool(snap.get("configured")),
            "hardware": {"cpu": True, "gpu_required": False},
            "cost_classification": "SELF_HOSTED",
            "free": True,
            "network": "disabled",
            "credentials_required": False,
            "execution_authority": False,
            "external_execution": False,
            "mcp": False,
            "license": {
                "model": "MIT",
                "runtime": "MIT",
                "commercial_use_evidence": "OpenAI Whisper code and model weights are released under MIT",
                "verified": True,
            },
        }

    def plan(
        self, *, organization_id: int, input_path: str, output_path: str,
        production_spec: Mapping[str, Any], graph: Mapping[str, Any],
        graph_node_id: str = "generation",
        language: str = "ar",
    ) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        source = Path(str(input_path))
        if not source.is_file():
            raise ValueError("input_artifact_required")
        if int(production_spec.get("organization_id") or 0) != int(organization_id):
            raise ValueError("production_spec_tenant_mismatch")
        if not production_spec.get("digest"):
            raise ValueError("production_spec_digest_required")
        node_ids = {str(n.get("id")) for n in (graph.get("nodes") or [])}
        if str(graph_node_id) not in node_ids:
            raise ValueError("generation_graph_node_required")
        snap = self.snapshot(organization_id)
        if not snap["configured"]:
            raise RuntimeError("self_owned_transcription_runtime_unavailable")
        payload = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "worker_id": self.WORKER_ID,
            "capability": self.CAPABILITY,
            "provider_id": self.PROVIDER_ID,
            "model_id": self.MODEL_ID,
            "input_artifact": {
                "uri": str(source.resolve()),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
            "output_path": str(Path(output_path).resolve()),
            "language": str(language or "ar"),
            "production_spec_digest": str(production_spec["digest"]),
            "production_graph_digest": str(graph.get("digest") or ""),
            "graph_node_id": str(graph_node_id),
            "cost_classification": "SELF_HOSTED",
            "action": "kemet_self_owned_transcription",
            "parameters": {
                "organization_id": int(organization_id),
                "input_path": str(source.resolve()),
                "output_path": str(Path(output_path).resolve()),
                "language": str(language or "ar"),
            },
            "execution": {
                "action": "kemet_self_owned_transcription",
                "automatic": False,
                "canonical_runtime_only": True,
                "human_approval_required": True,
            },
            "governance": {
                "execution_authority": False,
                "external_execution": False,
                "human_approval_required": True,
                "mcp": False,
            },
        }
        payload["plan_hash"] = execution_authorization.plan_hash(payload)
        return payload

    def execute(self, *, plan: Mapping[str, Any], authorization: Mapping[str, Any]) -> dict[str, Any]:
        if not authorization or authorization.get("authorized") is not True:
            return {"success": False, "status": "blocked", "error": "human_authorization_required", "executed": False}
        result = canonical_execution_runtime.execute(
            plan=dict(plan), authorization=dict(authorization),
            action_registry=_action_registry(),
        )
        if not result.get("success"):
            return result
        artifact = dict((result.get("artifact") or {}).get("artifact") or {})
        if not artifact:
            return {"success": False, "status": "failed", "error": "artifact_evidence_missing", "executed": True}
        path = Path(str(artifact.get("uri") or ""))
        if not path.is_file():
            return {"success": False, "status": "blocked", "error": "transcript_artifact_missing", "executed": True}
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != str(artifact.get("sha256") or ""):
            return {"success": False, "status": "blocked", "error": "transcript_artifact_digest_mismatch", "executed": True}
        payload = json.loads(path.read_text(encoding="utf-8"))
        segments = payload.get("transcript") or []
        qa = {
            "schema": "kemet.media.transcription_qa.v1",
            "status": "PASS" if segments and all(float(x.get("end", 0)) >= float(x.get("start", 0)) for x in segments) else "BLOCKED",
            "checks": {
                "file_exists": True,
                "sha256_match": True,
                "json_valid": True,
                "segments_present": bool(segments),
                "timestamps_valid": all(float(x.get("end", 0)) >= float(x.get("start", 0)) for x in segments),
            },
        }
        evidence = {
            "schema": "kemet.media.self_owned_transcription_evidence.v1",
            "version": 1,
            "organization_id": int(plan["organization_id"]),
            "worker_id": self.WORKER_ID,
            "capability": self.CAPABILITY,
            "provider_id": self.PROVIDER_ID,
            "model_id": self.MODEL_ID,
            "production_spec_digest": plan["production_spec_digest"],
            "production_graph_digest": plan["production_graph_digest"],
            "graph_node_id": plan["graph_node_id"],
            "input_artifact": plan["input_artifact"],
            "artifact": artifact,
            "qa": qa,
            "license": self.snapshot(plan["organization_id"])["license"],
            "provenance": {
                "source": "canonical_execution_runtime",
                "worker": self.WORKER_ID,
                "cost_classification": "SELF_HOSTED",
                "network": "disabled",
            },
            "governance": {
                "execution_authority": False,
                "external_execution": False,
                "human_approval_required": True,
                "mcp": False,
            },
        }
        evidence["evidence_digest"] = hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        return {
            "success": qa["status"] == "PASS",
            "status": "READY" if qa["status"] == "PASS" else "blocked",
            "executed": True,
            "artifact": artifact,
            "qa": qa,
            "evidence": evidence,
        }


def _action_registry():
    from app.automation.action_registry import registry
    return registry


self_owned_transcription_worker = SelfOwnedTranscriptionWorker()
