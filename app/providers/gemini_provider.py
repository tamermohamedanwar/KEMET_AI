from app.providers.base_provider import BaseProvider

class GeminiProvider(BaseProvider):

    def generate(self, prompt: str) -> str:
        return f"Gemini Provider: {prompt}"
