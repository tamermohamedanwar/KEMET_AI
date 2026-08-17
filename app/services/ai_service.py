from app.core.provider_factory import get_provider

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

def ask_ai(prompt: str, context: str = "", organization_id=None) -> str:
    provider = get_provider()

    full_prompt = f"""
{SYSTEM_PROMPT}

سياق المحادثة:
{context}


رسالة المستخدم:
{prompt}

الإجابة:
"""

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
