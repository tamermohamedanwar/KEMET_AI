from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MLGeneralizationAssessment:
    schema: str
    task: str
    model_family: str
    generalization_focus: tuple[str, ...]
    evaluation_requirements: tuple[str, ...]
    governance: dict[str, Any]
    digest: str


class MLGeneralizationIntelligence:
    VERSION = "1.0"
    SCHEMA = "kemet.ml.generalization_assessment.v1"

    @staticmethod
    def _digest(payload: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @classmethod
    def assess_svm(cls, *, task: str = "classification") -> dict[str, Any]:
        if task not in {"classification", "regression", "one_class"}:
            raise ValueError("unsupported_ml_task")
        focus = (
            "generalization",
            "model_complexity",
            "overfitting",
            "underfitting",
            "regularization",
            "data_quality",
            "class_balance",
        )
        requirements = (
            "separate_train_validation_test_evidence",
            "cross_validation_or_time_aware_validation",
            "feature_scaling_review",
            "hyperparameter_selection_without_test_leakage",
            "baseline_comparison",
            "precision_recall_f1_and_task_appropriate_metrics",
            "out_of_sample_error_analysis",
        )
        payload = {
            "schema": cls.SCHEMA,
            "version": cls.VERSION,
            "task": task,
            "model_family": "support_vector_machine",
            "generalization_focus": focus,
            "evaluation_requirements": requirements,
            "governance": {
                "advisory": True,
                "read_only": True,
                "external_execution": False,
                "auto_train": False,
                "auto_deploy": False,
                "human_review_required": True,
            },
        }
        return {**payload, "digest": cls._digest(payload)}

    @classmethod
    def compare_signal(cls, *, train_score: float, test_score: float) -> dict[str, Any]:
        train = float(train_score)
        test = float(test_score)
        if not (0.0 <= train <= 1.0 and 0.0 <= test <= 1.0):
            raise ValueError("score_out_of_range")
        gap = train - test
        if gap > 0.15:
            status = "generalization_gap_review_required"
        elif test < 0.50:
            status = "underfit_or_signal_insufficient_review_required"
        else:
            status = "no_large_observed_generalization_gap"
        return {
            "schema": "kemet.ml.generalization_signal.v1",
            "train_score": train,
            "test_score": test,
            "generalization_gap": round(gap, 6),
            "status": status,
            "advisory": True,
            "execution_authority": "none",
        }


ml_generalization_intelligence = MLGeneralizationIntelligence()
