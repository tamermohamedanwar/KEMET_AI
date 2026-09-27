from app.config.settings import AI_PRIMARY_PROVIDER, AI_PROVIDER, AI_REQUIRED_CAPABILITIES
from app.core.provider_factory import federated_generate, get_provider
from app.core.task_classifier import classify_task
from app.core.response_contract import response_contract

SYSTEM_PROMPT = """
أنت Kemet AI، المساعد الرسمي لمنصة Kemet AI للذكاء الاصطناعي.
اسم المشروع هو Kemet AI.
عند سؤال المستخدم عن اسمك أو مشروعك، أجب بأنك Kemet AI.

إذا وجدت معلومات داخل قسم (محتوى الملفات)
فاعتمد عليها أولاً.

إذا لم تجد معلومات كافية،
أخبر المستخدم بذلك ثم استخدم معرفتك العامة.

إذا كان طلب المستخدم يحتاج تنفيذ إجراء أو أتمتة:
أعد JSON فقط بهذا الشكل:

{
  "action": "اسم_الإجراء",
  "parameters": {
    "key": "value"
  }
}

الإجراءات المتاحة:
- check_order
- create_ticket

إذا كان الطلب سؤالاً عادياً:
أجب باللغة العربية بشكل طبيعي.

"""

RESPONSE_RULES = response_contract.system_rules()



def ask_ai(prompt: str, context: str = "", organization_id=None) -> str:
    full_prompt = f"""
{SYSTEM_PROMPT}

{RESPONSE_RULES}

سياق المحادثة:
{context}


رسالة المستخدم:
{prompt}

الإجابة:
"""

    if AI_PROVIDER.lower() == "federated":
        classified = classify_task(prompt)
        configured = frozenset(x.strip() for x in AI_REQUIRED_CAPABILITIES.split(",") if x.strip())
        capabilities = configured | classified.capabilities
        result = federated_generate(
            full_prompt,
            preferred=AI_PRIMARY_PROVIDER,
            required_capabilities=capabilities,
            organization_id=organization_id,
        )
        return result.content

    provider = get_provider()
    return provider.generate(full_prompt)


def parse_automation_response(response):
    """
    Parse AI automation response safely.
    """
    if not response:
        return {}
    if isinstance(response, dict):
        return response
    import json
    try:
        data = json.loads(response)
        if isinstance(data, dict) and "action" in data:
            return data
    except Exception:
        pass
    return {}
