from app.rag.rag_service import rag_service
from app.services.ai_service import ask_ai


class AgentService:
    """
    المرحلة الأولى:
    - يجمع سياق RAG.
    - يطلب الرد من Kemet AI.
    - يعيد نتيجة موحدة.
    """

    def handle(self, message: str):
        context = rag_service.get_context(message)

        reply = ask_ai(
            prompt=message,
            context=context,
        )

        return {
            "action": "reply",
            "reply": reply,
            "context": context,
        }


agent_service = AgentService()
