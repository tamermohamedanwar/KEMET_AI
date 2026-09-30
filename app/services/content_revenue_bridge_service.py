from __future__ import annotations

from typing import Any, Mapping

from app.services.content_commercial_loop_service import content_commercial_loop_service
from app.services.publication_measurement_evidence_service import publication_measurement_evidence_service


class ContentRevenueBridgeService:
    """Read-only bridge from authoritative provider measurement to verified content revenue evidence."""

    VERSION = "1.0"

    def measure_and_attribute(
        self,
        *,
        organization_id: int,
        user_id: int,
        channel: str,
        content_id: str,
        publication_id: str,
        execution_key: str,
        payment_evidence: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        if int(user_id) <= 0:
            raise ValueError("user_required")
        if not str(content_id or "").strip():
            raise ValueError("content_id_required")
        if not str(publication_id or "").strip():
            raise ValueError("publication_id_required")
        if not str(execution_key or "").strip():
            raise ValueError("execution_key_required")
        if channel not in {"facebook", "instagram"}:
            raise ValueError("authoritative_channel_not_supported")

        measurement = publication_measurement_evidence_service.verify(
            organization_id=int(organization_id),
            user_id=int(user_id),
            execution_key=str(execution_key),
            channel=str(channel),
            publication_id=str(publication_id),
        )
        if measurement.get("success") is not True or measurement.get("verified") is not True:
            return {
                "success": False,
                "status": "blocked",
                "error": measurement.get("error") or "authoritative_measurement_failed",
                "organization_id": int(organization_id),
                "content_id": str(content_id),
                "publication_id": str(publication_id),
                "execution_key": str(execution_key),
                "governance": self._governance(),
            }

        metrics = self._map_metrics(measurement.get("metrics") or {})
        evidence = self._bind_payment_evidence(
            content_id=str(content_id),
            payment_evidence=payment_evidence or [],
        )
        result = content_commercial_loop_service.evaluate(
            organization_id=int(organization_id),
            content_id=str(content_id),
            channel=str(channel),
            publication_id=str(publication_id),
            metrics=metrics,
            payment_evidence=evidence,
        )
        result["provider_measurement"] = {
            "verified": True,
            "provider": measurement.get("provider") or "meta_graph",
            "channel": str(channel),
            "publication_id": str(publication_id),
            "execution_key": str(execution_key),
            "publication_evidence_id": measurement.get("publication_evidence_id"),
            "metric_evidence_digest": measurement.get("metric_evidence_digest"),
            "metric_provenance": measurement.get("metric_provenance") or {},
            "synthetic": False,
        }
        result["governance"] = self._governance()
        return result

    @staticmethod
    def _map_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
        views = metrics.get("views")
        if views is None:
            views = metrics.get("post_impressions")
        qualified_views = metrics.get("reach")
        if qualified_views is None:
            qualified_views = metrics.get("post_reach")
        return {
            "views": views,
            "qualified_views": qualified_views,
            "watch_time_seconds": metrics.get("watch_time_seconds"),
            "retention_rate": metrics.get("retention_rate"),
            "followers_gained": metrics.get("followers_gained"),
        }

    @staticmethod
    def _bind_payment_evidence(
        *,
        content_id: str,
        payment_evidence: list[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        bound: list[dict[str, Any]] = []
        for item in payment_evidence:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("stage") or "") != "payment.completed":
                continue
            receipt = dict(item.get("receipt") or {})
            bound_content_id = str(item.get("content_id") or receipt.get("content_id") or "")
            provider_transaction_id = str(
                item.get("provider_transaction_id") or receipt.get("provider_transaction_id") or ""
            ).strip()
            if bound_content_id != content_id or not provider_transaction_id:
                continue
            receipt["content_id"] = content_id
            receipt["provider_transaction_id"] = provider_transaction_id
            bound.append({**dict(item), "receipt": receipt})
        return bound

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "read_only": True,
            "tenant_scoped": True,
            "external_execution": False,
            "execution_authority": False,
            "human_approval_required_for_actions": True,
            "causal_claim": False,
            "roi_claim": False,
        }


content_revenue_bridge_service = ContentRevenueBridgeService()
