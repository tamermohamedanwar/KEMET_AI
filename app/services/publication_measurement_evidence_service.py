from __future__ import annotations

from hashlib import sha256
from typing import Any

from app.services.publication_evidence_service import publication_evidence_service
from app.services.social_measurement_service import MeasurementRequest, social_measurement_service


class PublicationMeasurementEvidenceService:
    VERSION = "1.0"

    def verify(
        self,
        *,
        organization_id: int,
        user_id: int,
        execution_key: str,
        channel: str,
        publication_id: str,
    ) -> dict[str, Any]:
        if int(organization_id) <= 0 or int(user_id) <= 0:
            raise ValueError("measurement_identity_required")
        key = str(execution_key or "").strip()
        clean_channel = str(channel or "").strip().lower()
        requested_publication = str(publication_id or "").strip()
        if not key or clean_channel not in {"facebook", "instagram"} or not requested_publication:
            raise ValueError("measurement_binding_required")

        publication = publication_evidence_service.verify(
            organization_id=int(organization_id),
            execution_key=key,
            channel=clean_channel,
        )
        if publication.get("verified") is not True:
            return self._blocked("publication_evidence_missing", publication)

        records = [
            row for row in publication.get("records", [])
            if row.get("publication_id") == requested_publication
            and row.get("channel") == clean_channel
        ]
        if not records:
            return self._blocked("publication_identity_mismatch", publication)

        measurement = social_measurement_service.measure(
            MeasurementRequest(
                int(organization_id),
                int(user_id),
                clean_channel,
                requested_publication,
            )
        )
        if measurement.get("success") is not True or measurement.get("verified") is not True:
            return self._blocked(
                measurement.get("error") or "authoritative_measurement_failed",
                publication,
            )

        metrics = measurement.get("metrics") or {}
        metric_digest = sha256(repr(sorted(metrics.items())).encode()).hexdigest()
        return {
            "success": True,
            "status": "measurement_verified",
            "verified": True,
            "organization_id": int(organization_id),
            "user_id": int(user_id),
            "execution_key": key,
            "channel": clean_channel,
            "provider": records[0].get("provider") or "meta_graph",
            "publication_id": requested_publication,
            "publication_evidence_id": records[0].get("evidence_id"),
            "metrics": metrics,
            "metric_provenance": measurement.get("metric_provenance") or {},
            "metric_evidence_digest": metric_digest,
            "synthetic": False,
            "revenue_verified": False,
            "governance": self._governance(),
        }

    def verify_telegram_admin_measurement(
        self,
        *,
        organization_id: int,
        user_id: int,
        execution_key: str,
        publication_id: str,
        metrics: dict[str, Any],
        source_ref: str,
        human_verified: bool,
    ) -> dict[str, Any]:
        if int(organization_id) <= 0 or int(user_id) <= 0:
            raise ValueError("measurement_identity_required")
        if not str(execution_key or "").strip() or not str(publication_id or "").strip():
            raise ValueError("measurement_binding_required")
        if not isinstance(metrics, dict) or not metrics:
            raise ValueError("telegram_metrics_required")
        if not str(source_ref or "").strip() or human_verified is not True:
            return self._blocked("telegram_admin_verification_required", {})
        publication = publication_evidence_service.verify(
            organization_id=int(organization_id), execution_key=str(execution_key), channel="telegram"
        )
        if publication.get("verified") is not True:
            return self._blocked("publication_evidence_missing", publication)
        records = [row for row in publication.get("records", []) if row.get("publication_id") == str(publication_id)]
        if not records:
            return self._blocked("publication_identity_mismatch", publication)
        digest = sha256(repr(sorted(metrics.items())).encode()).hexdigest()
        return {
            "success": True, "status": "measurement_verified", "verified": True,
            "organization_id": int(organization_id), "user_id": int(user_id),
            "execution_key": str(execution_key), "channel": "telegram",
            "publication_id": str(publication_id), "publication_evidence_id": records[0].get("evidence_id"),
            "metrics": dict(metrics), "metric_provenance": {k: "TELEGRAM_ADMIN_VERIFIED" for k in metrics},
            "metric_evidence_digest": digest, "synthetic": False, "revenue_verified": False,
            "source_ref": str(source_ref)[:500], "human_verified": True, "governance": self._governance(),
        }

    @staticmethod
    def _blocked(error: str, publication: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": False,
            "status": "blocked",
            "verified": False,
            "error": error,
            "publication_evidence": publication,
            "governance": PublicationMeasurementEvidenceService._governance(),
        }

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "read_only": True,
            "tenant_scoped": True,
            "external_execution": False,
            "financial_action": False,
            "causal_claim": False,
            "roi_claim": False,
        }


publication_measurement_evidence_service = PublicationMeasurementEvidenceService()
