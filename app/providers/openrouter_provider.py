import os
import requests

class AIProviderResponse(str):
    def __new__(cls, content, tokens=0):
        obj = str.__new__(cls, content)
        obj.tokens = int(tokens or 0)
        return obj



class OpenRouterProvider:

    def generate(self, prompt):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": os.getenv("AI_MODEL", "openai/gpt-4o-mini"),
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                },
                timeout=30
            )

            print("STATUS:", response.status_code)
            print("BODY:", response.text)
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
            print("AI PROVIDER ERROR:", e)
            return "حدث خطأ مؤقت في خدمة الذكاء الاصطناعي. حاول مرة أخرى."
