from __future__ import annotations

from typing import Any

from app.services.ml_dataset_authorization_service import MLDatasetAuthorizationService
from app.services.ml_evaluation_record_service import ml_evaluation_record_service
from app.services.ml_evaluation_evidence_service import ml_evaluation_evidence_service
from app.services.ml_evaluation_persistence_service import ml_evaluation_persistence_service


class MLEvaluationCapability:
    VERSION = "1.1"
    CAPABILITY_ID = "ml_evaluation"
    EXECUTION_AUTHORITY = "none"
    INTAKE_SCHEMA = "kemet.ml.dataset_intake.v1"

    @classmethod
    def snapshot(cls) -> dict[str, Any]:
        return {
            "version": cls.VERSION,
            "capability_id": cls.CAPABILITY_ID,
            "purpose": "evidence_based_ml_model_evaluation",
            "status": "available_for_governed_evaluation",
            "execution_authority": cls.EXECUTION_AUTHORITY,
            "governance": {
                "advisory": True,
                "read_only": True,
                "auto_train": False,
                "auto_deploy": False,
                "policy_mutation": False,
                "human_review_required": True,
            },
            "record_schema": ml_evaluation_record_service.SCHEMA,
            "intake_schema": cls.INTAKE_SCHEMA,
        }

    @classmethod
    def evaluate_record(cls, **kwargs: Any) -> dict[str, Any]:
        record = ml_evaluation_record_service.build(**kwargs)
        return {
            "capability": cls.snapshot(),
            "record": record,
            "control_chain": ml_evaluation_record_service.control_chain(record),
        }

    @classmethod
    def evaluate_complete_record(cls, *, authorization_record: dict[str, Any], evidence: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        organization_id = kwargs.get("organization_id")
        dataset_digest = kwargs.get("dataset_digest")
        if not MLDatasetAuthorizationService.can_enter_evaluation(authorization_record, organization_id=organization_id):
            raise ValueError("ml_dataset_authorization_required")
        if dataset_digest != authorization_record.get("dataset_sha256"):
            raise ValueError("ml_dataset_digest_mismatch")
        completed = ml_evaluation_evidence_service.build(
            organization_id=organization_id, task_id=kwargs["task_id"], dataset_digest=dataset_digest,
            baseline=kwargs["baseline"], model_results=kwargs["model_results"],
            leakage_evidence=evidence["leakage_evidence"], generalization_evidence=evidence["generalization_evidence"],
            error_analysis=evidence["error_analysis"],
            provenance={**dict(kwargs.get("provenance") or {}), **dict(evidence.get("provenance") or {}), "dataset_digest": dataset_digest},
        )
        result = cls.evaluate_authorized_record(authorization_record=authorization_record, **kwargs)
        result["evidence_completion"] = completed
        result["record"]["evidence_completion_digest"] = completed["evidence_digest"]
        result["record"]["status"] = "evidence_complete_review_required"
        result["control_chain"] = ml_evaluation_record_service.control_chain({**result["record"], "status": "review_required"})
        return result

    @classmethod
    def persist_complete_record(cls, *, authorization_record: dict[str, Any], evidence: dict[str, Any], intake_record: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        if authorization_record.get("organization_id") != kwargs.get("organization_id"):
            raise ValueError("ml_tenant_mismatch")
        evaluation_key = str(kwargs.pop("evaluation_key", kwargs.get("task_id", ""))).strip()
        result = cls.evaluate_complete_record(authorization_record=authorization_record, evidence=evidence, **kwargs)
        result["record"]["evaluation_key"] = evaluation_key
        stored = ml_evaluation_persistence_service.persist(
            evaluation=result["record"],
            authorization_record=authorization_record,
            intake_record=intake_record,
        )
        result["persistence"] = {
            "stored": True,
            "record_id": stored.id,
            "evaluation_key": stored.evaluation_key,
            "organization_id": stored.organization_id,
            "status": stored.status,
            "approval_status": stored.approval_status,
            "execution_status": stored.execution_status,
        }
        return result

    @classmethod
    def evaluate_authorized_record(cls, *, authorization_record: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        organization_id = kwargs.get("organization_id")
        dataset_digest = kwargs.get("dataset_digest")
        if not MLDatasetAuthorizationService.can_enter_evaluation(
            authorization_record, organization_id=organization_id
        ):
            raise ValueError("ml_dataset_authorization_required")
        if dataset_digest != authorization_record.get("dataset_sha256"):
            raise ValueError("ml_dataset_digest_mismatch")
        kwargs["provenance"] = {
            **dict(kwargs.get("provenance") or {}),
            "dataset_authorization": {
                "authorization_reference": authorization_record["authorization_reference"],
                "authorization_digest": authorization_record["digest"],
            },
        }
        return cls.evaluate_record(**kwargs)

    @classmethod
    def evaluate_intake(
        cls,
        *,
        intake_record: dict[str, Any],
        authorization_record: dict[str, Any],
        split_strategy: str,
        baseline: dict[str, Any],
        model_results: list[dict[str, Any]],
        leakage_check: str,
        generalization: dict[str, Any],
    ) -> dict[str, Any]:
        if intake_record.get("schema") != cls.INTAKE_SCHEMA:
            raise ValueError("ml_dataset_intake_required")
        if intake_record.get("status") != "ready_for_governed_evaluation":
            raise ValueError("ml_dataset_intake_not_ready")
        if not MLDatasetAuthorizationService.can_enter_evaluation(
            authorization_record,
            organization_id=intake_record.get("organization_id"),
        ):
            raise ValueError("ml_dataset_authorization_required")
        if intake_record.get("authorization_reference") != authorization_record.get("authorization_reference"):
            raise ValueError("ml_authorization_reference_mismatch")
        if intake_record.get("dataset_digest") != authorization_record.get("dataset_sha256"):
            raise ValueError("ml_dataset_digest_mismatch")
        return cls.evaluate_authorized_record(
            authorization_record=authorization_record,
            organization_id=intake_record["organization_id"],
            task_id=intake_record["task_id"],
            dataset_digest=intake_record["dataset_digest"],
            split_strategy=split_strategy,
            baseline=baseline,
            model_results=model_results,
            leakage_check=leakage_check,
            generalization=generalization,
            provenance={
                "dataset_intake": {
                    "digest": intake_record["digest"],
                    "authorization_reference": intake_record["authorization_reference"],
                }
            },
        )


ml_evaluation_capability = MLEvaluationCapability()
