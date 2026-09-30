from __future__ import annotations

from typing import Any

from app.services.ml_evaluation_capability import ml_evaluation_capability



class MLDecisionReviewService:
    VERSION = "1.0"
    SCHEMA = "kemet.ml.decision_review.v1"

    @classmethod
    def build_empty_review(cls, *, organization_id: int) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        snapshot = ml_evaluation_capability.snapshot()
        persisted = None
        try:
            from flask import has_app_context
            if has_app_context():
                from app.services.ml_evaluation_persistence_service import ml_evaluation_persistence_service
                persisted = ml_evaluation_persistence_service.get_latest_for_organization(organization_id=int(organization_id))
        except Exception:
            persisted = None
        if persisted is not None:
            return {
                "schema": cls.SCHEMA, "version": cls.VERSION, "organization_id": int(organization_id),
                "decision_id": persisted.evaluation_key, "evaluation_id": str(persisted.id),
                "authorization_reference": persisted.authorization_reference,
                "dataset_sha256": persisted.dataset_sha256,
                "evidence_digest": persisted.evidence_digest,
                "evidence_completion_digest": persisted.evidence_completion_digest,
                "evidence_completion_status": "complete" if persisted.evidence_completion_digest else "not_complete",
                "leakage_evidence_status": "observed" if persisted.evidence_completion_digest else "not_available",
                "generalization_evidence_status": "observed" if persisted.evidence_completion_digest else "not_available",
                "error_analysis_status": "observed" if persisted.evidence_completion_digest else "not_available",
                "provenance_binding_status": "bound",
                "decision_status": persisted.status, "approval_status": persisted.approval_status,
                "execution_status": persisted.execution_status, "evidence_status": "observed" if persisted.evidence_digest else "not_available",
                "outcome_status": "not_observed", "learning_status": "advisory",
                "review_only": True, "execution_authority": "none", "human_review_required": True,
                "authorized_dataset_present": True, "benchmark_status": "evidence_complete_review_required" if persisted.evidence_completion_digest else "review_required",
                "control_evidence_chain": [
                    {"stage": "decision", "status": persisted.status, "id": persisted.evaluation_digest},
                    {"stage": "approval", "status": persisted.approval_status, "id": None},
                    {"stage": "execution", "status": persisted.execution_status, "id": None},
                    {"stage": "evidence", "status": "observed" if persisted.evidence_digest else "not_available", "id": persisted.evidence_digest},
                    {"stage": "outcome", "status": "not_observed", "id": None},
                    {"stage": "learning", "status": "advisory", "id": persisted.evaluation_digest},
                ],
                "governance": snapshot.get("governance", {}),
            }
        return {
            "schema": cls.SCHEMA,
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "decision_id": None,
            "evaluation_id": None,
            "authorization_reference": None,
            "dataset_sha256": None,
            "evidence_digest": None,
            "evidence_completion_digest": None,
            "evidence_completion_status": "not_available_until_authorized_dataset",
            "leakage_evidence_status": "not_available_until_authorized_dataset",
            "generalization_evidence_status": "not_available_until_authorized_dataset",
            "error_analysis_status": "not_available_until_authorized_dataset",
            "provenance_binding_status": "not_available_until_authorized_dataset",
            "decision_status": "review_required",
            "approval_status": "pending",
            "execution_status": "not_executed",
            "evidence_status": "not_available_until_authorized_dataset",
            "outcome_status": "not_observed",
            "learning_status": "advisory",
            "review_only": True,
            "execution_authority": "none",
            "human_review_required": True,
            "authorized_dataset_present": False,
            "benchmark_status": "blocked_until_authorized_dataset",
            "control_evidence_chain": [
                {"stage": "decision", "status": "review_required", "id": None},
                {"stage": "approval", "status": "pending", "id": None},
                {"stage": "execution", "status": "not_executed", "id": None},
                {"stage": "evidence", "status": "not_available_until_authorized_dataset", "id": None},
                {"stage": "outcome", "status": "not_observed", "id": None},
                {"stage": "learning", "status": "advisory", "id": None},
            ],
            "governance": snapshot.get("governance", {}),
        }


ml_decision_review_service = MLDecisionReviewService()
