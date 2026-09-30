from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.evidence.fabric import execution_evidence_fabric


class MLEvaluationRecordService:
    VERSION = "1.0"
    SCHEMA = "kemet.ml.evaluation_record.v1"

    @staticmethod
    def _digest(payload: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

    @classmethod
    def build(
        cls,
        *,
        organization_id: int,
        task_id: str,
        dataset_digest: str,
        split_strategy: str,
        baseline: dict[str, Any],
        model_results: list[dict[str, Any]],
        leakage_check: str,
        generalization: dict[str, Any],
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if organization_id <= 0 or not task_id.strip():
            raise ValueError("ml_identity_required")
        if len(dataset_digest) != 64 or any(c not in "0123456789abcdef" for c in dataset_digest.lower()):
            raise ValueError("dataset_digest_required")
        if split_strategy not in {"train_validation_test", "cross_validation", "time_aware"}:
            raise ValueError("unsupported_split_strategy")
        if leakage_check not in {"passed", "review_required", "failed", "not_run"}:
            raise ValueError("unsupported_leakage_status")
        if not isinstance(model_results, list):
            raise ValueError("model_results_required")
        payload = {
            "schema": cls.SCHEMA,
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "task_id": task_id.strip(),
            "dataset_digest": dataset_digest.lower(),
            "split_strategy": split_strategy,
            "baseline": dict(baseline),
            "model_results": [dict(item) for item in model_results],
            "leakage_check": leakage_check,
            "generalization": dict(generalization),
            "provenance": dict(provenance or {}),
            "status": "review_required",
            "governance": {
                "advisory": True,
                "read_only": True,
                "external_execution": False,
                "auto_train": False,
                "auto_deploy": False,
                "policy_mutation": False,
                "human_review_required": True,
                "causal_claim": False,
            },
        }
        evidence = execution_evidence_fabric.context_package(
            task_id=task_id,
            organization_id=organization_id,
            policy={"ml_evaluation": "advisory_review_only"},
            routing={"model_selection": "evidence_based_review"},
            sources=[{"type": "dataset", "digest": dataset_digest.lower()}],
        )
        payload["evidence_digest"] = evidence["digest"]
        payload["decision_boundary"] = "no_deployment_without_human_review"
        return {**payload, "digest": cls._digest(payload)}

    @classmethod
    def control_chain(cls, record: dict[str, Any]) -> dict[str, Any]:
        if record.get("schema") != cls.SCHEMA or record.get("status") != "review_required":
            raise ValueError("invalid_ml_evaluation_record")
        correlation = execution_evidence_fabric.correlation_context(
            trace_id=record["task_id"], organization_id=record["organization_id"], evidence_id=record["evidence_digest"]
        )
        return execution_evidence_fabric.control_chain(
            correlation=correlation,
            stages=[
                {"stage": "decision", "status": "review_required", "id": record["digest"]},
                {"stage": "approval", "status": "pending", "id": None},
                {"stage": "execution", "status": "not_executed", "id": None},
                {"stage": "evidence", "status": "observed", "id": record["evidence_digest"]},
                {"stage": "learning", "status": "advisory", "id": record["digest"]},
            ],
        )


ml_evaluation_record_service = MLEvaluationRecordService()
