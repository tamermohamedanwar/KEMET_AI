from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.ml_dataset_authorization_service import MLDatasetAuthorizationService


class MLDatasetIntakeService:
    VERSION = "1.1"
    SCHEMA = "kemet.ml.dataset_intake.v1"
    EXECUTION_AUTHORITY = "none"

    @staticmethod
    def _digest(payload: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _validate_shape(*, organization_id: int, dataset_id: str, dataset_digest: str, row_count: int, feature_count: int, target: str) -> None:
        if organization_id <= 0 or not dataset_id.strip() or not target.strip():
            raise ValueError("dataset_identity_required")
        if len(dataset_digest) != 64 or any(c not in "0123456789abcdef" for c in dataset_digest.lower()):
            raise ValueError("dataset_digest_required")
        if row_count <= 0 or feature_count <= 0:
            raise ValueError("dataset_shape_required")

    @classmethod
    def assess(cls, *, organization_id: int, dataset_id: str, dataset_digest: str, row_count: int, feature_count: int, target: str, source_type: str = "external_authorized") -> dict[str, Any]:
        cls._validate_shape(
            organization_id=organization_id,
            dataset_id=dataset_id,
            dataset_digest=dataset_digest,
            row_count=row_count,
            feature_count=feature_count,
            target=target,
        )
        if source_type not in {"internal_authorized", "external_authorized", "synthetic_fixture"}:
            raise ValueError("unsupported_dataset_source")
        authorized_entry = source_type != "synthetic_fixture"
        payload = {
            "schema": cls.SCHEMA,
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "dataset_id": dataset_id.strip(),
            "dataset_digest": dataset_digest.lower(),
            "row_count": int(row_count),
            "feature_count": int(feature_count),
            "target": target.strip(),
            "source_type": source_type,
            "status": "review_required",
            "authorized_entry": authorized_entry,
            "governance": {
                "advisory": True,
                "read_only": True,
                "execution_authority": cls.EXECUTION_AUTHORITY,
                "training_authority": False,
                "deployment_authority": False,
                "human_review_required": True,
            },
        }
        return {**payload, "digest": cls._digest(payload)}

    @classmethod
    def build_authorized_intake(
        cls,
        *,
        authorization_record: dict[str, Any],
        organization_id: int,
        dataset_id: str,
        dataset_digest: str,
        row_count: int,
        feature_count: int,
        target: str,
        task_id: str,
        business_task: str,
        baseline_required: bool = True,
        evaluation_plan: dict[str, Any] | None = None,
        generalization_requirements: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cls._validate_shape(
            organization_id=organization_id,
            dataset_id=dataset_id,
            dataset_digest=dataset_digest,
            row_count=row_count,
            feature_count=feature_count,
            target=target,
        )
        if not task_id.strip() or not business_task.strip():
            raise ValueError("ml_task_identity_required")
        if not MLDatasetAuthorizationService.can_enter_evaluation(
            authorization_record, organization_id=organization_id
        ):
            raise ValueError("ml_dataset_authorization_required")
        if authorization_record.get("dataset_id") != dataset_id.strip():
            raise ValueError("ml_dataset_identity_mismatch")
        if authorization_record.get("dataset_sha256") != dataset_digest.lower():
            raise ValueError("ml_dataset_digest_mismatch")
        if not authorization_record.get("authorization_reference"):
            raise ValueError("ml_authorization_reference_required")

        payload = {
            "schema": cls.SCHEMA,
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "dataset_id": dataset_id.strip(),
            "dataset_digest": dataset_digest.lower(),
            "authorization_reference": authorization_record["authorization_reference"],
            "authorization_digest": authorization_record.get("digest"),
            "task_id": task_id.strip(),
            "business_task": business_task.strip(),
            "target": target.strip(),
            "row_count": int(row_count),
            "feature_count": int(feature_count),
            "baseline_required": bool(baseline_required),
            "evaluation_plan": dict(evaluation_plan or {}),
            "generalization_requirements": dict(generalization_requirements or {}),
            "status": "ready_for_governed_evaluation",
            "benchmark_status": "not_run",
            "governance": {
                "advisory": True,
                "read_only": True,
                "execution_authority": cls.EXECUTION_AUTHORITY,
                "training_authority": False,
                "deployment_authority": False,
                "policy_mutation": False,
                "human_review_required": True,
            },
            "control_chain": {
                "decision": "review_required",
                "approval": "pending",
                "execution": "not_executed",
                "evidence": "intake_recorded",
                "outcome": "not_observed",
                "learning": "advisory",
            },
        }
        return {**payload, "digest": cls._digest(payload)}


ml_dataset_intake_service = MLDatasetIntakeService()
