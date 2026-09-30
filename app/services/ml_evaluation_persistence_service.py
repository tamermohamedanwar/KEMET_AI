from __future__ import annotations

import json
from typing import Any

from app import db
from app.models.ml_evaluation_record import MLEvaluationRecord


class MLEvaluationPersistenceService:
    VERSION = "1.0"

    @staticmethod
    def _organization_id(record: dict[str, Any]) -> int:
        value = record.get("organization_id")
        if not isinstance(value, int) or value <= 0:
            raise ValueError("ml_identity_required")
        return value

    @classmethod
    def persist(cls, *, evaluation: dict[str, Any], authorization_record: dict[str, Any], intake_record: dict[str, Any] | None = None) -> MLEvaluationRecord:
        org_id = cls._organization_id(evaluation)
        if authorization_record.get("status") != "authorized" or authorization_record.get("human_review_status") != "approved":
            raise ValueError("ml_dataset_authorization_required")
        if authorization_record.get("organization_id") != org_id:
            raise ValueError("ml_tenant_mismatch")
        if evaluation.get("dataset_digest") != authorization_record.get("dataset_sha256"):
            raise ValueError("ml_dataset_digest_mismatch")
        if intake_record is not None:
            if intake_record.get("organization_id") != org_id:
                raise ValueError("ml_intake_tenant_mismatch")
            if intake_record.get("dataset_digest") != evaluation.get("dataset_digest"):
                raise ValueError("ml_intake_dataset_digest_mismatch")
            if intake_record.get("authorization_reference") != authorization_record.get("authorization_reference"):
                raise ValueError("ml_intake_authorization_mismatch")
        key = str(evaluation.get("evaluation_key") or evaluation.get("task_id") or "").strip()
        if not key:
            raise ValueError("evaluation_key_required")
        existing = MLEvaluationRecord.query.filter_by(organization_id=org_id, evaluation_key=key).one_or_none()
        if existing:
            if existing.evaluation_digest != evaluation.get("digest"):
                raise ValueError("ml_evaluation_idempotency_conflict")
            return existing
        payload = dict(evaluation)
        record = MLEvaluationRecord(
            organization_id=org_id,
            evaluation_key=key,
            task_id=str(evaluation["task_id"]),
            dataset_id=str(authorization_record["dataset_id"]),
            dataset_sha256=str(evaluation["dataset_digest"]),
            authorization_reference=str(authorization_record["authorization_reference"]),
            authorization_digest=str(authorization_record["digest"]),
            intake_digest=(intake_record or {}).get("digest"),
            evaluation_digest=str(evaluation["digest"]),
            evidence_digest=evaluation.get("evidence_digest"),
            evidence_completion_digest=evaluation.get("evidence_completion_digest") or (evaluation.get("evidence_completion") or {}).get("evidence_digest"),
            status=str(evaluation.get("status") or "review_required"),
            approval_status="pending",
            execution_status="not_executed",
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str),
        )
        db.session.add(record)
        db.session.flush()
        return record

    @classmethod
    def get_for_organization(cls, *, organization_id: int, evaluation_key: str) -> MLEvaluationRecord | None:
        if organization_id <= 0 or not evaluation_key.strip():
            raise ValueError("organization_required")
        return MLEvaluationRecord.query.filter_by(organization_id=organization_id, evaluation_key=evaluation_key.strip()).one_or_none()


ml_evaluation_persistence_service = MLEvaluationPersistenceService()
