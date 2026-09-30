from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ModelProfile:
    provider_id: str
    model_id: str
    capabilities: frozenset[str]
    priority: int = 0
    cost_tier: str = "standard"

    def supports(self, required: Iterable[str]) -> bool:
        return set(required).issubset(self.capabilities)


class ModelIntelligenceRegistry:
    VERSION = "1.0"

    def __init__(self, profiles: Iterable[ModelProfile] | None = None):
        self._profiles = tuple(profiles or self._defaults())

    @staticmethod
    def _defaults() -> tuple[ModelProfile, ...]:
        return (
            ModelProfile("openai", "gpt-5.6", frozenset({"reasoning", "coding", "agentic", "tool_calling", "long_context", "multimodal"}), 100, "premium"),
            ModelProfile("anthropic", "claude-sonnet-4-5", frozenset({"reasoning", "coding", "agentic", "tool_calling", "long_context"}), 95, "premium"),
            ModelProfile("google", "gemini-3.8-flash", frozenset({"reasoning", "coding", "agentic", "tool_calling", "long_context", "multimodal", "research"}), 92, "standard"),
            ModelProfile("xai", "grok-4.6", frozenset({"reasoning", "coding", "agentic", "tool_calling", "long_context", "research"}), 90, "premium"),
            ModelProfile("groq", "llama-4-scout", frozenset({"reasoning", "coding", "agentic", "tool_calling", "long_context"}), 88, "standard"),
            ModelProfile("mistral", "mistral-large", frozenset({"reasoning", "coding", "tool_calling", "long_context", "multimodal"}), 86, "standard"),
            ModelProfile("deepseek", "deepseek-chat", frozenset({"reasoning", "coding", "tool_calling", "long_context"}), 84, "standard"),
            ModelProfile("cohere", "command-a", frozenset({"reasoning", "coding", "tool_calling", "long_context", "research"}), 82, "standard"),
            ModelProfile("perplexity", "sonar", frozenset({"reasoning", "research", "long_context", "tool_calling"}), 80, "standard"),
            ModelProfile("qwen", "qwen-plus", frozenset({"reasoning", "coding", "agentic", "tool_calling", "long_context", "multimodal"}), 78, "standard"),
            ModelProfile("meta", "llama-4-maverick", frozenset({"reasoning", "coding", "agentic", "tool_calling", "multimodal"}), 85, "standard"),
            ModelProfile("meta", "llama-4-scout", frozenset({"reasoning", "coding", "agentic", "tool_calling", "long_context", "multimodal"}), 84, "standard"),
            ModelProfile("groq", "llama-4-maverick", frozenset({"reasoning", "coding", "agentic", "tool_calling", "multimodal"}), 78, "standard"),
            ModelProfile("mistral", "mistral-large", frozenset({"reasoning", "coding", "agentic", "tool_calling", "long_context"}), 76, "standard"),
            ModelProfile("deepseek", "deepseek-chat", frozenset({"reasoning", "coding", "tool_calling", "long_context"}), 74, "standard"),
            ModelProfile("deepseek", "deepseek-reasoner", frozenset({"reasoning", "coding", "long_context"}), 73, "premium"),
            ModelProfile("qwen", "qwen-max", frozenset({"reasoning", "coding", "agentic", "tool_calling", "long_context", "multimodal"}), 70, "standard"),
        )

    def all(self) -> tuple[ModelProfile, ...]:
        return tuple(sorted(self._profiles, key=lambda item: (-item.priority, item.provider_id, item.model_id)))

    def for_provider(self, provider_id: str) -> tuple[ModelProfile, ...]:
        return tuple(item for item in self.all() if item.provider_id == provider_id)

    def get(self, provider_id: str, model_id: str) -> ModelProfile | None:
        return next((item for item in self._profiles if item.provider_id == provider_id and item.model_id == model_id), None)

    def snapshot(self) -> list[dict[str, object]]:
        return [{"provider_id": item.provider_id, "model_id": item.model_id,
                 "capabilities": sorted(item.capabilities), "priority": item.priority,
                 "cost_tier": item.cost_tier} for item in self.all()]


model_intelligence = ModelIntelligenceRegistry()
