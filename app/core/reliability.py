from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ERROR_CATEGORIES = frozenset({
    "validation_error", "authentication_error", "authorization_error",
    "approval_required", "governance_blocked", "dependency_error",
    "provider_error", "database_error", "timeout", "configuration_error",
    "internal_error", "unavailable", "rate_limited",
})


@dataclass(frozen=True)
class ReliabilityObservation:
    operation: str
    status: str
    duration_ms: float | None = None
    error_category: str | None = None
    retries: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error_category": normalize_error_category(self.error_category),
            "retries": max(0, int(self.retries)),
        }


def normalize_error_category(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip().lower()
    return candidate if candidate in ERROR_CATEGORIES else "internal_error"


def classify_exception(exc: BaseException) -> str:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "timeout" in name or "timeout" in text:
        return "timeout"
    if "rate" in name or "rate_limit" in text or "too many" in text:
        return "rate_limited"
    if "database" in name or "sql" in name or "db" in name:
        return "database_error"
    if "auth" in name or "credential" in text:
        return "authentication_error"
    return "internal_error"


class ReliabilitySnapshot:
    VERSION = "1.0"
    SCHEMA = "kemet.reliability_snapshot.v1"

    def summarize(self, observations: list[ReliabilityObservation]) -> dict[str, Any]:
        total = len(observations)
        successes = sum(1 for item in observations if item.status == "success")
        failures = total - successes
        durations = sorted(
            item.duration_ms for item in observations if item.duration_ms is not None
        )
        p95 = durations[max(0, int(len(durations) * 0.95) - 1)] if durations else None
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "measurement_only": True,
            "execution_authority": False,
            "total": total,
            "successes": successes,
            "failures": failures,
            "success_rate": (successes / total) if total else None,
            "p95_duration_ms": p95,
            "timeouts": sum(item.error_category == "timeout" for item in observations),
            "retries": sum(max(0, item.retries) for item in observations),
        }


reliability_snapshot = ReliabilitySnapshot()
