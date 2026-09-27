import os
import requests

from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.secret_boundary import redact

class AIProviderResponse(str):
    def __new__(cls, content, tokens=0):
        obj = str.__new__(cls, content)
        obj.tokens = int(tokens or 0)
        return obj



class OpenRouterProvider:

    def generate(self, prompt, model=None, system=None, context=()):
        try:
            endpoint = validate_public_http_target("https://openrouter.ai/api/v1/chat/completions", allow_hosts={"openrouter.ai"})
            response = governed_request("POST",
                endpoint,
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model or os.getenv("AI_MODEL", "openai/gpt-4o-mini"),
                    "messages": ([{"role": "system", "content": system}] if system else [])
                    + list(context or ())
                    + [{"role": "user", "content": prompt}],
                },
                timeout=30,
                allow_redirects=False
            )

            response.raise_for_status()

            data = response.json()
            usage = data.get("usage") or {}

            total_tokens = (
                usage.get("total_tokens")
                or (
                    int(usage.get("prompt_tokens", 0) or 0)
                    + int(usage.get("completion_tokens", 0) or 0)
                )
            )

            content = data["choices"][0]["message"]["content"]

            return AIProviderResponse(
                content,
                tokens=total_tokens,
            )

        except Exception as e:
            redact(str(e))
            return "حدث خطأ مؤقت في خدمة الذكاء الاصطناعي. حاول مرة أخرى."
