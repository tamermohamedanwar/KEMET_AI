from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class ProviderUsage:
    provider_id: str
    requests: int = 0
    successes: int = 0
    failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms_total: float = 0.0
    cost_usd_observed: float = 0.0
    cost_observations: int = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "requests": self.requests,
            "successes": self.successes,
            "failures": self.failures,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "avg_latency_ms": round(self.latency_ms_total / self.requests, 3) if self.requests else None,
            "cost_usd_observed": round(self.cost_usd_observed, 8),
            "cost_observations": self.cost_observations,
            "cost_status": (
                "not_observed" if not self.cost_observations
                else "observed" if self.cost_observations == self.successes
                else "partial_observation"
            ),
        }


class ProviderUsageTelemetry:
    VERSION = "1.0"

    def __init__(self):
        self._states: dict[str, ProviderUsage] = {}
        self._lock = Lock()

    def _state(self, provider_id: str) -> ProviderUsage:
        return self._states.setdefault(provider_id, ProviderUsage(provider_id))

    def record_success(self, provider_id: str, *, latency_ms: float, input_tokens: int = 0,
                       output_tokens: int = 0, total_tokens: int = 0,
                       observed_cost_usd: float | None = None) -> None:
        with self._lock:
            state = self._state(provider_id)
            state.requests += 1
            state.successes += 1
            state.latency_ms_total += max(0.0, float(latency_ms))
            state.input_tokens += max(0, int(input_tokens or 0))
            state.output_tokens += max(0, int(output_tokens or 0))
            state.total_tokens += max(0, int(total_tokens or 0))
            if observed_cost_usd is not None:
                state.cost_usd_observed += max(0.0, float(observed_cost_usd))
                state.cost_observations += 1

    def record_failure(self, provider_id: str, *, latency_ms: float) -> None:
        with self._lock:
            state = self._state(provider_id)
            state.requests += 1
            state.failures += 1
            state.latency_ms_total += max(0.0, float(latency_ms))

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._states[key].snapshot() for key in sorted(self._states)]

    def reset(self) -> None:
        with self._lock:
            self._states.clear()


provider_usage_telemetry = ProviderUsageTelemetry()
