from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


STATUS_NOT_CONNECTED = "NOT_CONNECTED"
STATUS_UNVERIFIED = "UNVERIFIED"
STATUS_CONNECTED_NO_DATA = "CONNECTED_NO_DATA"
STATUS_VERIFIED = "VERIFIED"


@dataclass(frozen=True)
class VisibilityMeasurement:
    source: str
    market: str
    language: str
    query: str
    timestamp: str
    visibility_signal: float | None
    mention: bool | None
    position_signal: float | None
    competitor_signal: float | None
    evidence: dict[str, Any] | None
    verified: bool


class RealVisibilityMeasurementService:
    VERSION = "1.0"
    SOURCES = ("google", "chatgpt", "gemini")
    STATUSES = (
        STATUS_NOT_CONNECTED,
        STATUS_UNVERIFIED,
        STATUS_CONNECTED_NO_DATA,
        STATUS_VERIFIED,
    )

    @classmethod
    def empty_snapshot(cls, organization_id: int | None, market: str = "global") -> dict[str, Any]:
        return {
            "version": cls.VERSION,
            "organization_id": organization_id,
            "market": market,
            "status": STATUS_NOT_CONNECTED,
            "measurements": [],
            "source_status": {source: STATUS_NOT_CONNECTED for source in cls.SOURCES},
            "contract": [
                "source", "market", "language", "query", "timestamp",
                "visibility_signal", "mention", "position_signal",
                "competitor_signal", "evidence", "verified",
            ],
            "governance": {
                "read_only": True,
                "tenant_scoped": True,
                "no_fabricated_metrics": True,
                "no_external_execution": True,
            },
        }

    @classmethod
    def normalize(cls, measurement: VisibilityMeasurement) -> dict[str, Any]:
        if measurement.source not in cls.SOURCES:
            raise ValueError("unsupported_visibility_source")
        if not measurement.market or not measurement.language or not measurement.query:
            raise ValueError("visibility_measurement_identity_required")
        if not measurement.timestamp:
            raise ValueError("visibility_measurement_timestamp_required")
        if measurement.verified and not measurement.evidence:
            raise ValueError("verified_visibility_requires_evidence")
        if measurement.verified and measurement.visibility_signal is None and measurement.mention is None:
            raise ValueError("verified_visibility_requires_signal")
        return asdict(measurement)

    @classmethod
    def new_timestamp(cls) -> str:
        return datetime.now(timezone.utc).isoformat()


real_visibility_measurement_service = RealVisibilityMeasurementService()
