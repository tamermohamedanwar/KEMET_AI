"""Canonical platform measurement normalization for Phase 3."""
from __future__ import annotations

from hashlib import sha256
from typing import Any

SCHEMA = "kemet.social_measurement_phase3.v1"


class SocialMeasurementPhase3Service:
    SCHEMA = SCHEMA

    def normalize(self, organization_id: int, channel: str,
                  metrics: dict[str, Any]) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_required")
        if not channel:
            raise ValueError("channel_required")
        if not isinstance(metrics, dict):
            raise ValueError("metrics_required")
        values = {
            "views": self._number(metrics.get("views")),
            "qualified_views": self._number(metrics.get("qualified_views")),
            "watch_time_seconds": self._number(metrics.get("watch_time_seconds")),
            "retention_rate": self._number(metrics.get("retention_rate")),
            "followers_gained": self._number(metrics.get("followers_gained")),
            "revenue": self._number(metrics.get("revenue")),
            "revenue_currency": metrics.get("revenue_currency"),
        }
        digest = sha256(repr(sorted(values.items())).encode()).hexdigest()
        return {
            "schema": self.SCHEMA,
            "organization_id": int(organization_id),
            "channel": channel,
            "metrics": values,
            "evidence_digest": digest,
            "revenue_is_authoritative": values["revenue"] is not None,
            "synthetic": False,
        }

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


social_measurement_phase3_service = SocialMeasurementPhase3Service()
