from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any


@dataclass(frozen=True)
class ProviderBudget:
    provider_id: str
    class_name: str
    free_or_low_cost: bool
    capabilities: tuple[str, ...]
    fallback_priority: int
    notes: str


class ProviderResilienceRegistry:
    VERSION = "1.0"
    FAILURE_CLASSES = frozenset({"rate_limit", "quota", "billing", "timeout", "unavailable", "auth", "model", "unknown"})

    def __init__(self):
        self._budgets = self._defaults()
        self._penalties: dict[str, float] = {}
        self._last_reason: dict[str, str] = {}

    @staticmethod
    def _defaults() -> dict[str, ProviderBudget]:
        return {
            "openai": ProviderBudget("openai", "frontier", False, ("reasoning", "coding", "multimodal"), 100, "primary when configured"),
            "anthropic": ProviderBudget("anthropic", "frontier", False, ("reasoning", "coding", "long_context"), 95, "specialist fallback"),
            "google": ProviderBudget("google", "frontier", True, ("reasoning", "coding", "multimodal", "research"), 90, "free tier varies by project and model"),
            "xai": ProviderBudget("xai", "frontier", False, ("reasoning", "research", "long_context"), 85, "paid/plan dependent"),
            "groq": ProviderBudget("groq", "inference", True, ("coding", "reasoning", "fast_inference"), 80, "free limits vary by account/model"),
            "openrouter": ProviderBudget("openrouter", "gateway", True, ("routing", "many_models"), 75, "free models and routing availability vary"),
            "huggingface": ProviderBudget("huggingface", "gateway", True, ("text", "image", "embeddings", "many_models"), 70, "free credits are limited and changeable"),
            "cloudflare": ProviderBudget("cloudflare", "inference", True, ("text", "image", "speech", "edge"), 65, "Workers AI free allocation is limited"),
            "deepseek": ProviderBudget("deepseek", "model_provider", False, ("reasoning", "coding", "long_context"), 60, "plan/billing dependent"),
            "qwen": ProviderBudget("qwen", "model_provider", False, ("reasoning", "coding", "multimodal"), 55, "plan/billing dependent"),
        }

    def catalog(self) -> list[dict[str, Any]]:
        return [budget.__dict__.copy() for budget in sorted(self._budgets.values(), key=lambda x: -x.fallback_priority)]

    def classify_failure(self, error: Exception) -> str:
        status = getattr(error, "status_code", None)
        if status == 429:
            return "rate_limit"
        if status in {402, 403}:
            return "billing"
        if status in {401}:
            return "auth"
        if status in {404}:
            return "model"
        name = type(error).__name__.lower()
        text = str(error).lower()
        if "quota" in text:
            return "quota"
        if "timeout" in text or "timed out" in text:
            return "timeout"
        if "unavailable" in text or "connection" in text:
            return "unavailable"
        return "unknown" if name else "unknown"

    def penalize(self, provider_id: str, failure_class: str, retry_after: float | None = None) -> None:
        failure_class = failure_class if failure_class in self.FAILURE_CLASSES else "unknown"
        base = {"rate_limit": 60, "quota": 300, "billing": 900, "timeout": 30, "unavailable": 45, "auth": 900, "model": 120, "unknown": 30}[failure_class]
        duration = max(base, float(retry_after or 0))
        self._penalties[provider_id] = monotonic() + duration
        self._last_reason[provider_id] = failure_class

    def available(self, provider_id: str) -> bool:
        return monotonic() >= self._penalties.get(provider_id, 0.0)

    def status(self) -> list[dict[str, Any]]:
        now = monotonic()
        return [{"provider_id": provider_id, "available": now >= until,
                 "cooldown_seconds": round(max(0.0, until - now), 2),
                 "last_failure_class": self._last_reason.get(provider_id)}
                for provider_id, until in sorted(self._penalties.items())]


provider_resilience = ProviderResilienceRegistry()
