from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
import os


@dataclass(frozen=True)
class ProviderProfile:
    provider_id: str
    display_name: str
    capabilities: frozenset[str]
    priority: int
    api_key_env: str | None = None
    enabled: bool = True
    primary: bool = False
    execution_ready: bool = True
    metadata: dict[str, str] = field(default_factory=dict)

    def supports(self, required: Iterable[str]) -> bool:
        return set(required).issubset(self.capabilities)

    def is_configured(self) -> bool:
        return bool(self.api_key_env and os.getenv(self.api_key_env))


class AIFederationRegistry:
    VERSION = "1.2"

    def __init__(self, profiles: Iterable[ProviderProfile] | None = None):
        self._profiles = {p.provider_id: p for p in (profiles or self._defaults())}

    @staticmethod
    def _defaults() -> tuple[ProviderProfile, ...]:
        common = frozenset({"reasoning", "coding", "tool_calling"})
        return (
            ProviderProfile("openai", "OpenAI", common | {"agentic", "long_context", "multimodal"}, 100, "OPENAI_API_KEY", primary=True, execution_ready=True),
            ProviderProfile("anthropic", "Anthropic", common | {"agentic", "long_context"}, 90, "ANTHROPIC_API_KEY", execution_ready=True),
            ProviderProfile("google", "Google", common | {"agentic", "long_context", "multimodal", "research"}, 80, "GOOGLE_API_KEY", execution_ready=True),
            ProviderProfile("xai", "xAI", common | {"agentic", "long_context", "research"}, 70, "XAI_API_KEY", execution_ready=True),
            ProviderProfile("meta", "Meta", frozenset({"coding", "agentic", "tool_calling"}), 60, "META_API_KEY", execution_ready=False),
            ProviderProfile("manus", "Manus", frozenset({"agentic", "research", "long_context", "tool_calling"}), 55, "MANUS_API_KEY", execution_ready=False),
            ProviderProfile("openrouter", "OpenRouter", common | {"long_context", "multimodal"}, 50, "OPENROUTER_API_KEY", metadata={"class": "model_gateway", "global": "true"}),
            ProviderProfile("codecraft", "CodeCraft", common | {"long_context", "multimodal"}, 49, "CODECRAFT_API_KEY", execution_ready=True, metadata={"class": "model_gateway", "global": "true", "protocol": "openai_chat_completions"}),
            ProviderProfile("groq", "Groq", common | {"agentic", "long_context"}, 48, "GROQ_API_KEY", execution_ready=True, metadata={"class": "inference_platform", "global": "true"}),
            ProviderProfile("mistral", "Mistral AI", common | {"agentic", "long_context", "multimodal", "research"}, 46, "MISTRAL_API_KEY", execution_ready=True, metadata={"class": "model_provider", "global": "true"}),
            ProviderProfile("microsoft", "Microsoft Azure AI", common | {"agentic", "long_context", "multimodal"}, 44, "AZURE_OPENAI_API_KEY", execution_ready=False),
            ProviderProfile("aws", "Amazon Bedrock", common | {"agentic", "long_context", "multimodal", "research"}, 43, "AWS_ACCESS_KEY_ID", execution_ready=False),
            ProviderProfile("ibm", "IBM watsonx", common | {"enterprise", "reasoning", "coding", "tool_calling"}, 42, "IBM_WATSONX_API_KEY", execution_ready=False),
            ProviderProfile("nvidia", "NVIDIA NIM", common | {"agentic", "long_context", "multimodal"}, 41, "NVIDIA_API_KEY", execution_ready=False),
            ProviderProfile("cerebras", "Cerebras", common | {"reasoning", "coding", "long_context"}, 40, "CEREBRAS_API_KEY", execution_ready=False),
            ProviderProfile("together", "Together AI", common | {"agentic", "long_context", "multimodal"}, 39, "TOGETHER_API_KEY", execution_ready=False),
            ProviderProfile("fireworks", "Fireworks AI", common | {"agentic", "long_context", "multimodal"}, 38, "FIREWORKS_API_KEY", execution_ready=False),
            ProviderProfile("moonshot", "Moonshot AI", common | {"reasoning", "coding", "long_context"}, 37, "MOONSHOT_API_KEY", execution_ready=False),
            ProviderProfile("deepseek", "DeepSeek", common | {"reasoning", "coding", "long_context"}, 44, "DEEPSEEK_API_KEY", execution_ready=True, metadata={"class": "model_provider", "global": "true"}),
            ProviderProfile("cohere", "Cohere", common | {"long_context", "research"}, 42, "COHERE_API_KEY", execution_ready=True, metadata={"class": "enterprise_ai", "global": "true"}),
            ProviderProfile("perplexity", "Perplexity", common | {"research", "long_context"}, 40, "PERPLEXITY_API_KEY", execution_ready=True, metadata={"class": "research_provider", "global": "true"}),
            ProviderProfile("qwen", "Alibaba Qwen", common | {"reasoning", "coding", "agentic", "long_context", "multimodal"}, 38, "QWEN_API_KEY", execution_ready=True, metadata={"class": "model_provider", "global": "true"}),
        )

    def get(self, provider_id: str) -> ProviderProfile | None:
        return self._profiles.get(provider_id)

    def all(self) -> tuple[ProviderProfile, ...]:
        return tuple(sorted(self._profiles.values(), key=lambda p: (-p.priority, p.provider_id)))

    def select(self, required_capabilities: Iterable[str] = (), *, preferred: str | None = None) -> ProviderProfile:
        required = tuple(required_capabilities)
        if preferred:
            candidate = self.get(preferred)
            if candidate and candidate.enabled and candidate.supports(required):
                return candidate
        candidates = [p for p in self.all() if p.enabled and p.supports(required)]
        if not candidates:
            raise LookupError("No enabled provider satisfies the requested capabilities")
        return candidates[0]

    def routing_snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "provider_id": p.provider_id,
                "display_name": p.display_name,
                "priority": p.priority,
                "primary": p.primary,
                "enabled": p.enabled,
                "execution_ready": p.execution_ready,
                "capabilities": sorted(p.capabilities),
                "api_key_env": p.api_key_env,
                "configured": p.is_configured(),
            }
            for p in self.all()
        ]


ai_federation = AIFederationRegistry()
