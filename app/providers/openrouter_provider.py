import os
import requests


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
            return data["choices"][0]["message"]["content"]

        except Exception as e:
            print("AI PROVIDER ERROR:", e)
            return "حدث خطأ مؤقت في خدمة الذكاء الاصطناعي. حاول مرة أخرى."
