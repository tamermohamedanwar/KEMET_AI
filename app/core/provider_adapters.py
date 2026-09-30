from __future__ import annotations

import os

from app.core.provider_adapter import ProviderAdapter
from app.core.provider_http_adapter import AnthropicAdapter, ChatCompletionsAdapter, GoogleInteractionsAdapter, ResponsesAPIAdapter
from app.core.provider_contracts import ProviderRequest, ProviderResponse
from app.providers.openrouter_provider import OpenRouterProvider


class LegacyOpenRouterAdapter(ProviderAdapter):
    provider_id = "openrouter"

    def __init__(self):
        self._provider = OpenRouterProvider()

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        content = self._provider.generate(
            request.prompt, model=request.model, system=request.system, context=request.context
        )
        return ProviderResponse(
            content=str(content),
            provider_id=self.provider_id,
            model=request.model or os.getenv("AI_MODEL"),
        )


def build_provider_adapters() -> dict[str, ProviderAdapter]:
    return {
        "openrouter": LegacyOpenRouterAdapter(),
        "codecraft": ChatCompletionsAdapter(
            "codecraft", "https://codecraftapi.com/v1", "CODECRAFT_API_KEY", os.getenv("CODECRAFT_MODEL", "gpt-5.6-sol")
        ),
        "openai": ResponsesAPIAdapter(
            "openai", "https://api.openai.com/v1", "OPENAI_API_KEY", os.getenv("OPENAI_MODEL", "gpt-5.6")
        ),
        "xai": ResponsesAPIAdapter(
            "xai", "https://api.x.ai/v1", "XAI_API_KEY", os.getenv("XAI_MODEL", "grok-4.6")
        ),
        "anthropic": AnthropicAdapter(os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")),
        "google": GoogleInteractionsAdapter(os.getenv("GOOGLE_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))),
        "groq": ResponsesAPIAdapter("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", os.getenv("GROQ_MODEL", "llama-4-scout")),
        "deepseek": ResponsesAPIAdapter("deepseek", "https://api.deepseek.com", "DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")),
        "mistral": ResponsesAPIAdapter("mistral", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", os.getenv("MISTRAL_MODEL", "mistral-large")),
        "perplexity": ResponsesAPIAdapter("perplexity", "https://api.perplexity.ai", "PERPLEXITY_API_KEY", os.getenv("PERPLEXITY_MODEL", "sonar")),
        "cohere": ResponsesAPIAdapter("cohere", "https://api.cohere.com/compatibility/v1", "COHERE_API_KEY", os.getenv("COHERE_MODEL", "command-a")),
        "qwen": ResponsesAPIAdapter("qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1", "QWEN_API_KEY", os.getenv("QWEN_MODEL", "qwen-plus")),
    }


class FederatedProvider(ProviderAdapter):
    def __init__(self, adapter: ProviderAdapter, provider_id: str):
        self._adapter = adapter
        self.provider_id = provider_id

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        return self._adapter.generate(request)
