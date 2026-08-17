from app.providers.base_provider import BaseProvider

class OllamaProvider(BaseProvider):

    def generate(self, prompt: str) -> str:
        return f"Ollama Provider: {prompt}"
