import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_chatgpt(prompt):
    r = client.chat.completions.create(
        model=os.getenv("CHATGPT_MODEL", "gpt-4o-mini"),
        messages=[
            {"role":"system","content":"انت مساعد Kemet_AI للكتابة والمحتوى"},
            {"role":"user","content":prompt}
        ]
    )
    return r.choices[0].message.content

def ask_meta(prompt):
    # هنا ميتا AI للتحليل والقرار
    return f"تحليل ميتا: الطلب '{prompt}' محتاج تنفيذ عبر Kemet OS"

def kemet_brain(prompt):
    gpt = ask_chatgpt(prompt)
    meta = ask_meta(prompt)
    final = f"""🤖 ChatGPT:\n{gpt}\n\n🧠 Meta:\n{meta}\n\n⚖️ Kemet القرار: اشتغل على {prompt[:50]}"""
    return final

if __name__ == "__main__":
    while True:
        q = input("\nانت: ")
        if q in ["exit","خروج"]: break
        print(kemet_brain(q))
