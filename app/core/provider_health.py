from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Mapping


@dataclass
class ProviderHealth:
    provider_id: str
    failures: int = 0
    successes: int = 0
    cooldown_until: float = 0.0
    last_error: str | None = None
    last_latency_ms: float | None = None

    @property
    def healthy(self) -> bool:
        return monotonic() >= self.cooldown_until


class ProviderHealthRegistry:
    VERSION = "1.1"

    def __init__(self, *, failure_threshold: int = 2, cooldown_seconds: float = 30.0):
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(1.0, cooldown_seconds)
        self._states: dict[str, ProviderHealth] = {}

    def state(self, provider_id: str) -> ProviderHealth:
        return self._states.setdefault(provider_id, ProviderHealth(provider_id))

    def is_healthy(self, provider_id: str) -> bool:
        return self.state(provider_id).healthy

    def record_success(self, provider_id: str, *, latency_ms: float | None = None) -> None:
        state = self.state(provider_id)
        state.successes += 1
        state.failures = 0
        state.cooldown_until = 0.0
        state.last_error = None
        if latency_ms is not None:
            state.last_latency_ms = max(0.0, float(latency_ms))

    def record_failure(self, provider_id: str, error: Exception | str, *, latency_ms: float | None = None, cooldown_seconds: float | None = None) -> None:
        state = self.state(provider_id)
        state.failures += 1
        state.last_error = getattr(error, "failure_class", None) or type(error).__name__ if isinstance(error, Exception) else str(error)
        if latency_ms is not None:
            state.last_latency_ms = max(0.0, float(latency_ms))
        if state.failures >= self.failure_threshold:
            state.cooldown_until = monotonic() + max(self.cooldown_seconds, float(cooldown_seconds or 0))

    def snapshot(self) -> list[Mapping[str, object]]:
        return [
            {
                "provider_id": state.provider_id,
                "healthy": state.healthy,
                "failures": state.failures,
                "successes": state.successes,
                "cooldown_seconds": round(max(0.0, state.cooldown_until - monotonic()), 3),
                "last_error_type": state.last_error,
                "last_latency_ms": state.last_latency_ms,
            }
            for state in sorted(self._states.values(), key=lambda item: item.provider_id)
        ]

    def reset(self, provider_id: str) -> None:
        self._states.pop(provider_id, None)


provider_health = ProviderHealthRegistry()
