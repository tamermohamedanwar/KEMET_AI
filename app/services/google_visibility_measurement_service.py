from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class GoogleMeasurement:
    source: str
    market: str
    language: str
    query: str
    timestamp: str
    visibility_signal: str
    mention: bool | None
    position_signal: float | None
    competitor_signal: Any
    evidence: dict[str, Any]
    verified: bool


class GoogleVisibilityMeasurementService:
    VERSION = "1.0"
    SOURCE = "google_search_console"

    @classmethod
    def build_measurement(
        cls,
        organization_id: int,
        market: str,
        language: str,
        query: str,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        clicks = row.get("clicks")
        impressions = row.get("impressions")
        position = row.get("position")
        verified = bool(row.get("verified_source"))
        measurement = GoogleMeasurement(
            source=cls.SOURCE,
            market=market,
            language=language,
            query=query,
            timestamp=timestamp,
            visibility_signal="search_console_performance",
            mention=None,
            position_signal=float(position) if position is not None else None,
            competitor_signal=None,
            evidence={
                "organization_id": organization_id,
                "clicks": clicks,
                "impressions": impressions,
                "source_verified": verified,
                "source_contract": "Google Search Console API",
            },
            verified=verified,
        )
        return {
            "source": measurement.source,
            "market": measurement.market,
            "language": measurement.language,
            "query": measurement.query,
            "timestamp": measurement.timestamp,
            "visibility_signal": measurement.visibility_signal,
            "mention": measurement.mention,
            "position_signal": measurement.position_signal,
            "competitor_signal": measurement.competitor_signal,
            "evidence": measurement.evidence,
            "verified": measurement.verified,
        }


def build_youtube_evidence(organization_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    verified = payload.get("verified_source") is True and payload.get("source") == "youtube_analytics_api"
    return {
        "source": "youtube_analytics_api",
        "market": "global",
        "language": "und",
        "query": "channel==MINE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "visibility_signal": "owned_channel_performance",
        "mention": None,
        "position_signal": None,
        "competitor_signal": None,
        "evidence": {
            "organization_id": organization_id,
            "period": payload.get("period"),
            "rows": payload.get("rows", []),
            "headers": payload.get("headers", []),
            "source_verified": verified,
        },
        "verified": verified,
    }
