from __future__ import annotations

import hashlib
import json
from typing import Any


class MLEvaluationEvidenceService:
    VERSION = "1.0"
    SCHEMA = "kemet.ml.evaluation_evidence.v1"
    REQUIRED = (
        "baseline",
        "model_results",
        "leakage_evidence",
        "generalization_evidence",
        "error_analysis",
        "provenance",
    )

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
        baseline: dict[str, Any],
        model_results: list[dict[str, Any]],
        leakage_evidence: dict[str, Any],
        generalization_evidence: dict[str, Any],
        error_analysis: dict[str, Any],
        provenance: dict[str, Any],
    ) -> dict[str, Any]:
        if organization_id <= 0 or not task_id.strip():
            raise ValueError("ml_identity_required")
        if len(dataset_digest) != 64 or any(c not in "0123456789abcdef" for c in dataset_digest.lower()):
            raise ValueError("dataset_digest_required")
        if not isinstance(baseline, dict) or not baseline:
            raise ValueError("baseline_evidence_required")
        if not isinstance(model_results, list) or not model_results or any(not isinstance(item, dict) or not item for item in model_results):
            raise ValueError("model_results_evidence_required")
        for name, value in (
            ("leakage_evidence", leakage_evidence),
            ("generalization_evidence", generalization_evidence),
            ("error_analysis", error_analysis),
            ("provenance", provenance),
        ):
            if not isinstance(value, dict) or not value:
                raise ValueError(f"{name}_required")
        if leakage_evidence.get("status") not in {"passed", "review_required"}:
            raise ValueError("leakage_evidence_incomplete")
        if not generalization_evidence.get("validation_strategy"):
            raise ValueError("generalization_evidence_incomplete")
        if not error_analysis.get("out_of_sample"):
            raise ValueError("error_analysis_incomplete")
        if provenance.get("dataset_digest") != dataset_digest.lower():
            raise ValueError("provenance_dataset_digest_mismatch")
        payload = {
            "schema": cls.SCHEMA,
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "task_id": task_id.strip(),
            "dataset_digest": dataset_digest.lower(),
            "baseline": dict(baseline),
            "model_results": [dict(item) for item in model_results],
            "leakage_evidence": dict(leakage_evidence),
            "generalization_evidence": dict(generalization_evidence),
            "error_analysis": dict(error_analysis),
            "provenance": dict(provenance),
            "status": "evidence_complete_review_required",
            "governance": {
                "advisory": True,
                "read_only": True,
                "execution_authority": "none",
                "auto_train": False,
                "auto_deploy": False,
                "human_review_required": True,
            },
        }
        return {**payload, "evidence_digest": cls._digest(payload)}


ml_evaluation_evidence_service = MLEvaluationEvidenceService()
