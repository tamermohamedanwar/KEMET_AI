from app.config.settings import AI_PROVIDER
from app.providers.ollama_provider import OllamaProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.openrouter_provider import OpenRouterProvider

def get_provider():
    providers = {
        "ollama": OllamaProvider,
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
    }

    provider = providers.get(AI_PROVIDER.lower())

    if not provider:
        raise ValueError(f"Unknown provider: {AI_PROVIDER}")

    return provider()
