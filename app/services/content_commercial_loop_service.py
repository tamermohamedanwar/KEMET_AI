from __future__ import annotations

from typing import Any, Mapping

from app.services.content_revenue_attribution_service import content_revenue_attribution_service
from app.services.social_measurement_phase3_service import social_measurement_phase3_service
from app.core.execution_evidence import execution_evidence
from app.services.publication_measurement_evidence_service import publication_measurement_evidence_service
from app.services.revenue_identity_reconciliation_service import revenue_identity_reconciliation_service


class ContentCommercialLoopService:
    """Read-only bridge from verified distribution measurement to verified commerce evidence."""

    VERSION = "1.0"

    def evaluate_verified(
        self,
        *,
        organization_id: int,
        user_id: int,
        content_id: str,
        channel: str,
        publication_id: str,
        execution_key: str,
    ) -> dict[str, Any]:
        if int(user_id) <= 0:
            raise ValueError("user_required")
        if not str(execution_key or "").strip():
            raise ValueError("execution_key_required")
        if channel not in {"facebook", "instagram"}:
            raise ValueError("authoritative_channel_not_supported")
        history = execution_evidence.history(
            organization_id=int(organization_id), execution_key=str(execution_key)
        )
        measurement = publication_measurement_evidence_service.verify(
            organization_id=int(organization_id),
            user_id=int(user_id),
            execution_key=str(execution_key),
            channel=str(channel),
            publication_id=str(publication_id),
        )
        if measurement.get("success") is not True or measurement.get("verified") is not True:
            return {
                "success": False, "status": "blocked",
                "error": measurement.get("error") or "authoritative_measurement_failed",
                "organization_id": int(organization_id), "content_id": str(content_id),
                "publication_id": str(publication_id), "execution_key": str(execution_key),
                "governance": self._governance(),
            }
        payment_evidence = [
            row for row in history
            if row.get("stage") == "payment.completed"
            and isinstance(row.get("receipt"), dict)
        ]
        result = self.evaluate(
            organization_id=int(organization_id), content_id=str(content_id),
            channel=str(channel), publication_id=str(publication_id),
            metrics=measurement.get("metrics") or {}, payment_evidence=payment_evidence,
        )
        reconciliation = revenue_identity_reconciliation_service.reconcile(
            organization_id=int(organization_id), content_id=str(content_id),
            publication_id=str(publication_id), execution_key=str(execution_key),
            evidence=history,
        )
        result["execution_key"] = str(execution_key)
        result["reconciliation"] = reconciliation
        result["provider_measurement"] = {
            "verified": True, "provider": measurement.get("provider") or "meta_graph",
            "channel": str(channel), "publication_id": str(publication_id),
            "execution_key": str(execution_key),
            "publication_evidence_id": measurement.get("publication_evidence_id"),
            "metric_evidence_digest": measurement.get("metric_evidence_digest"),
            "metric_provenance": measurement.get("metric_provenance") or {},
            "synthetic": False,
        }
        result["governance"] = self._governance()
        return result

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "read_only": True, "tenant_scoped": True, "external_execution": False,
            "execution_authority": False, "human_approval_required_for_actions": True,
            "causal_claim": False, "roi_claim": False,
        }

    def evaluate(
        self,
        *,
        organization_id: int,
        content_id: str,
        channel: str,
        publication_id: str,
        metrics: Mapping[str, Any],
        payment_evidence: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        measurement = social_measurement_phase3_service.normalize(
            int(organization_id), channel, dict(metrics or {})
        )
        attribution = content_revenue_attribution_service.evaluate(
            content_id=str(content_id),
            metrics={
                "views": measurement["metrics"].get("views") or 0,
                "qualified_views": measurement["metrics"].get("qualified_views") or 0,
                "conversions": 0,
            },
            payment_evidence=payment_evidence or [],
        )
        return {
            "success": True,
            "engine": "kemet_content_commercial_loop",
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "content_id": str(content_id),
            "publication": {
                "channel": channel,
                "publication_id": str(publication_id),
                "measurement_schema": measurement["schema"],
                "evidence_digest": measurement["evidence_digest"],
                "metric_provenance": "OBSERVED",
            },
            "commercial": attribution,
            "governance": {
                "read_only": True,
                "tenant_scoped": True,
                "external_execution": False,
                "execution_authority": False,
                "causal_claim": False,
            },
        }


content_commercial_loop_service = ContentCommercialLoopService()
