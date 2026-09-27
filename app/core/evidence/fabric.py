from __future__ import annotations

import hashlib
import json
from typing import Any


class EvidenceFabric:
    """Create deterministic, tamper-evident execution evidence."""

    VERSION = "1.0"

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

    def digest(self, payload: dict[str, Any]) -> str:
        return hashlib.sha256(self._canonical(payload).encode("utf-8")).hexdigest()

    def source_package(self, *, task_id: str, organization_id: int, evidences: list[dict[str, Any]], policy_fingerprint: str | None = None) -> dict[str, Any]:
        package = {
            "version": self.VERSION,
            "type": "external_source_evidence",
            "task_id": task_id,
            "organization_id": organization_id,
            "policy_fingerprint": policy_fingerprint,
            "sources": evidences,
        }
        return {**package, "digest": self.digest(package)}

    def context_package(
        self,
        *,
        task_id: str,
        organization_id: int,
        policy: dict[str, Any],
        routing: dict[str, Any],
        sources: list[dict[str, Any]] | None = None,
        project_context_hash: str | None = None,
    ) -> dict[str, Any]:
        package = {
            "version": self.VERSION,
            "type": "governed_context_evidence",
            "task_id": task_id,
            "organization_id": organization_id,
            "policy": policy,
            "routing": routing,
            "project_context_hash": project_context_hash,
            "sources": sources or [],
        }
        return {**package, "digest": self.digest(package)}

    def execution_record(
        self,
        *,
        action: str,
        plan_hash: str | None,
        risk: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        evidence = {
            "version": self.VERSION,
            "type": "execution_evidence",
            "action": action,
            "plan_hash": plan_hash,
            "risk": risk,
            "status": result.get("status"),
            "success": bool(result.get("success")),
            "executed": bool(result.get("executed")),
        }
        return {**evidence, "digest": self.digest(evidence)}


    def correlation_context(self, *, trace_id: str, span_id: str | None = None, organization_id: int | None = None,
                            task_id: str | None = None, assignment_id: str | None = None,
                            approval_id: str | None = None, execution_id: str | None = None,
                            evidence_id: str | None = None, outcome_id: str | None = None) -> dict[str, Any]:
        context = {
            "trace_id": str(trace_id), "span_id": str(span_id) if span_id else None,
            "organization_id": int(organization_id) if organization_id is not None else None,
            "task_id": str(task_id) if task_id else None, "assignment_id": str(assignment_id) if assignment_id else None,
            "approval_id": str(approval_id) if approval_id else None, "execution_id": str(execution_id) if execution_id else None,
            "evidence_id": str(evidence_id) if evidence_id else None, "outcome_id": str(outcome_id) if outcome_id else None,
        }
        if not context["trace_id"].strip():
            raise ValueError("trace_id_required")
        return context

    def control_chain(self, *, correlation: dict[str, Any], stages: list[dict[str, Any]]) -> dict[str, Any]:
        allowed = {"decision", "approval", "execution", "evidence", "outcome", "learning"}
        normalized = []
        for stage in stages:
            name = str(stage.get("stage") or "").strip().lower()
            if name not in allowed:
                raise ValueError("unsupported_control_stage")
            normalized.append({"stage": name, "status": str(stage.get("status") or "unknown"),
                               "id": str(stage.get("id")) if stage.get("id") is not None else None})
        package = {"version": self.VERSION, "type": "control_evidence_chain",
                   "correlation": dict(correlation), "stages": normalized}
        return {**package, "digest": self.digest(package)}


execution_evidence_fabric = EvidenceFabric()
