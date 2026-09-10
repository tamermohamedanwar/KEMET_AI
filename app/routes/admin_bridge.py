from flask import Blueprint, render_template_string, jsonify, request
from flask_login import login_required
from flask_wtf.csrf import generate_csrf
from app.admin.decorators import admin_required
from app.services.ai_service import ask_ai
import requests
import os
import json
import re

admin_bridge = Blueprint("admin_bridge", __name__)

AGENT_URL = os.getenv(
    "KEMET_AGENT_URL",
    "http://127.0.0.1:8765"
).rstrip("/")

TOKEN = os.getenv("KEMET_AGENT_TOKEN", "")


def agent_request(method, endpoint, payload=None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.request(
        method,
        f"{AGENT_URL}{endpoint}",
        headers=headers,
        json=payload,
        timeout=180,
    )

    try:
        data = response.json()
    except Exception:
        data = {
            "ok": response.ok,
            "text": response.text,
        }

    return data, response.status_code


def extract_json(text):
    text = str(text or "").strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.S)

    if match:
        return json.loads(match.group(0))

    raise ValueError("AI did not return valid JSON")


def project_context():
    context_parts = []

    try:
        data, _ = agent_request(
            "POST",
            "/run",
            {"command": "list_files"}
        )
        context_parts.append(
            "PROJECT FILES:\n" +
            json.dumps(data, ensure_ascii=False)[:30000]
        )
    except Exception:
        pass

    try:
        data, _ = agent_request(
            "POST",
            "/run",
            {"command": "git_status"}
        )
        context_parts.append(
            "GIT STATUS:\n" +
            json.dumps(data, ensure_ascii=False)[:10000]
        )
    except Exception:
        pass

    return "\n\n".join(context_parts)


def build_plan(task):
    context = project_context()

    prompt = f"""
You are the execution planner for Kemet AI.

The user gave this task:

{task}

Current project context:

{context}

Your job is to create a concrete implementation plan that can be executed
directly inside the existing Kemet AI project.

You have an authorized Termux Agent connected to this Kemet AI project.

The Agent can safely perform the following authorized operations:

FILE OPERATIONS:
- write or modify project files through the writes array
- create new project files when required
- read/search project context supplied by the Agent

AUTHORIZED COMMANDS:
- health
- git_status
- compile
- test_health

You ARE AUTHORIZED to include any of the commands above in the "commands" array when they are relevant to the user's task.

IMPORTANT:
- Do not refuse a task merely because it requires checking the project or running one of the authorized commands.
- Use "git_status" when the user asks for project/Git status.
- Use "compile" when the user asks to check Python compilation or validate Python syntax.
- Use "health" when the user asks to check service health.
- Use "test_health" when the user asks to test the application health endpoint.
- If the user explicitly says not to modify files, return an empty "writes" array and use only the necessary authorized commands.

You may:
- create files
- modify files
- create HTML/CSS/JS
- create Python/Flask code
- create APIs
- create database models/migrations when needed
- create bots and automation workflows
- create dashboards
- create reports
- create statistics
- create comparisons
- fix existing code
- improve existing UI
- create documentation
- create tests

IMPORTANT:
Return ONLY valid JSON.
No markdown.
No explanations outside JSON.

JSON format:

{{
  "summary": "short description",
  "writes": [
    {{
      "path": "relative/path/file.ext",
      "content": "complete file content"
    }}
  ],
  "commands": [
    "compile",
    "test_health"
  ]
}}

Rules:
- Never write secrets.
- Never modify .env, .env.local, .env.agent, or .git/config.
- Use paths relative to the project root.
- Prefer modifying existing project architecture instead of creating duplicates.
- If the user asks to create, add, change, modify, fix, update, or implement something, this is a WRITE task.
- WRITE tasks MUST contain at least one real object in the "writes" array.
- Never claim that a WRITE task was completed when "writes" is empty.
- For every file that must be changed, return its COMPLETE final content in the writes array.
- Do not return an empty writes array for a requested modification unless the task explicitly forbids modifications.
- Keep the implementation coherent with Flask/Kemet AI.
- Do not return placeholder text such as TODO.
- For UI work, make the result production-quality and responsive.
- For reports/statistics/comparisons, create a useful persistent artifact in the project.
- For bots, create the actual implementation, not just a description.
"""

    reply = ask_ai(prompt=prompt, context=context)
    plan = extract_json(reply)

    if not isinstance(plan, dict):
        plan = {}

    commands = plan.get("commands", [])
    if not isinstance(commands, list):
        commands = []

    normalized_commands = [str(command).strip() for command in commands if str(command).strip()]

    task_lower = task.lower()

    # Ensure explicit requests for authorized read/check operations
    # are translated into actual Agent commands even if the AI planner
    # fails to include them.
    if any(term in task_lower for term in (
        "git", "جيت", "حالة git", "حالة الملفات", "حالة المشروع"
    )):
        if "git_status" not in normalized_commands:
            normalized_commands.append("git_status")

    if any(term in task_lower for term in (
        "compile", "compilation", "syntax", "compileall",
        "ترجمة", "تجميع", "فحص بايثون", "فحص syntax"
    )):
        if "compile" not in normalized_commands:
            normalized_commands.append("compile")

    if any(term in task_lower for term in (
        "health", "service health", "صحة الخدمة", "حالة الخدمة"
    )):
        if "health" not in normalized_commands:
            normalized_commands.append("health")

    if any(term in task_lower for term in (
        "test health", "اختبار health", "اختبر health",
        "اختبار صحة التطبيق"
    )):
        if "test_health" not in normalized_commands:
            normalized_commands.append("test_health")

    # Search is an authorized verification command.
    if any(term in task_lower for term in (
        "search_code", "search code", "ابحث عن", "تحقق من وجود",
        "تحقق باستخدام search_code"
    )):
        if "search_code" not in normalized_commands:
            normalized_commands.append("search_code")

    plan["commands"] = normalized_commands

    # Detect whether this is explicitly a read-only task.
    read_only = any(term in task_lower for term in (
        "لا تعدل", "لا تعديل", "لا تغيّر", "لا تغير",
        "بدون تعديل", "دون تعديل", "لا تكتب", "read only",
        "read-only", "no changes", "do not modify", "don't modify"
    ))

    # Explicit no-modification requests must never generate writes.
    if read_only:
        plan["writes"] = []

    # A modification request without actual writes is not a successful plan.
    # Do not allow the UI to falsely report that a requested change was made.
    if not read_only:
        writes = plan.get("writes", [])
        if not isinstance(writes, list):
            writes = []

        normalized_writes = []
        for item in writes:
            if not isinstance(item, dict):
                continue

            path = str(item.get("path") or "").strip()
            content = item.get("content")

            if path and isinstance(content, str):
                normalized_writes.append({
                    "path": path,
                    "content": content,
                })

        plan["writes"] = normalized_writes

        if not normalized_writes:
            plan["_write_required"] = True
            plan["summary"] = (
                "تعذر إنشاء خطة كتابة فعلية لهذه المهمة؛ "
                "لم يُرجع المخطط أي ملف للتعديل."
            )

    return plan


def execute_plan(plan, approved=False, approver_id=None):
    if not approved:
        return {
            "ok": True,
            "stage": "approval",
            "status": "waiting_approval",
            "summary": plan.get("summary", ""),
            "writes": [],
            "commands": [],
            "approval": {
                "required": bool(plan.get("writes")),
                "approved": False,
                "approver_id": approver_id,
            },
            "execution": {
                "allowed": False,
                "executed": False,
                "external_execution": False,
                "database_mutation": False,
            },
        }

    results = []
    results = []

    if plan.get("_write_required"):
        return {
            "ok": False,
            "stage": "planning",
            "summary": plan.get("summary", ""),
            "writes": [],
            "commands": [],
            "error": "write_plan_empty",
        }

    writes = plan.get("writes", [])

    if not isinstance(writes, list):
        raise ValueError("writes must be a list")

    for item in writes:
        if not isinstance(item, dict):
            continue

        path = str(item.get("path") or "").strip()
        content = item.get("content")

        if not path or not isinstance(content, str):
            results.append({
                "ok": False,
                "error": "invalid_write_operation",
                "path": path,
            })
            continue

        data, code = agent_request(
            "POST",
            "/files/write",
            {
                "path": path,
                "content": content,
            },
        )

        results.append({
            "path": path,
            "status_code": code,
            "result": data,
        })

        if code >= 400 or not data.get("ok"):
            return {
                "ok": False,
                "stage": "write",
                "results": results,
            }

    commands = plan.get("commands", [])

    command_results = []

    allowed_commands = {
        "compile",
        "test_health",
        "git_status",
        "health",
        "search_code",
    }

    for command in commands:
        command = str(command)

        if command not in allowed_commands:
            command_results.append({
                "ok": False,
                "command": command,
                "error": "command_not_allowed",
            })
            continue

        data, code = agent_request(
            "POST",
            "/run",
            {"command": command},
        )

        command_results.append({
            "command": command,
            "status_code": code,
            "result": data,
        })

    return {
        "ok": True,
        "summary": plan.get("summary", ""),
        "writes": results,
        "commands": command_results,
    }


HTML = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Kemet AI — Execution Center</title>

<style>
*{box-sizing:border-box}

body{
    margin:0;
    min-height:100vh;
    background:#080d19;
    color:#eef2ff;
    font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}

.wrap{
    width:min(1150px,100%);
    margin:auto;
    padding:20px;
}

.card{
    background:#111a2d;
    border:1px solid #273653;
    border-radius:20px;
    padding:22px;
    margin-bottom:16px;
    box-shadow:0 12px 40px rgba(0,0,0,.18);
}

h1{
    margin:0 0 8px;
    font-size:28px;
}

h2{
    margin-top:0;
}

.sub{
    color:#9ba9c4;
    line-height:1.7;
}

.status{
    display:inline-flex;
    margin-top:15px;
    padding:8px 13px;
    border-radius:999px;
    background:#1b2942;
    font-weight:800;
}

.online{
    color:#4ade80;
}

.offline{
    color:#fb7185;
}

textarea{
    width:100%;
    min-height:180px;
    resize:vertical;
    background:#080d19;
    color:#fff;
    border:1px solid #34415d;
    border-radius:15px;
    padding:16px;
    font:inherit;
    line-height:1.7;
    outline:none;
}

textarea:focus{
    border-color:#7168ff;
}

.actions{
    display:flex;
    gap:10px;
    flex-wrap:wrap;
    margin-top:14px;
}

button{
    border:0;
    border-radius:13px;
    padding:13px 19px;
    cursor:pointer;
    font-weight:800;
    font-size:15px;
}

.primary{
    background:#635bff;
    color:#fff;
}

.secondary{
    background:#263653;
    color:#fff;
}

pre{
    margin:0;
    background:#060a12;
    color:#dbe5ff;
    padding:16px;
    border-radius:14px;
    overflow:auto;
    white-space:pre-wrap;
    word-break:break-word;
    direction:ltr;
    text-align:left;
    max-height:600px;
}

.capabilities{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:10px;
}

.cap{
    background:#0b1220;
    border:1px solid #24324e;
    padding:14px;
    border-radius:13px;
}

@media(max-width:750px){
    .wrap{padding:10px}
    .card{padding:17px}
    .capabilities{grid-template-columns:1fr}
}
</style>
</head>

<body>

<div class="wrap">

<div class="card">

<h1>⚡ Kemet AI Execution Center</h1>

<div class="sub">
اكتب المطلوب فقط. Kemet AI يفهم المهمة، يخطط لها، ينفذ التعديلات
مباشرة داخل المشروع، ثم يفحص النتيجة.
</div>

<div id="status" class="status">
جاري فحص Agent...
</div>

</div>

<div class="card">

<h2>🚀 اطلب أي شيء</h2>

<textarea id="task"
placeholder="مثال:
اعمل لي بوت خدمة عملاء عربي داخل Kemet AI مع واجهة محادثة، حفظ المحادثات، وربطه بقاعدة البيانات.

أو:
اعمل Dashboard للإحصائيات والمبيعات بتصميم احترافي ومتجاوب.

أو:
افحص المشروع وأصلح أي أخطاء في نظام تسجيل الدخول.

أو:
اعمل مقارنة بين خطط الاشتراك الحالية وأنشئ صفحة مقارنة احترافية."></textarea>

<div class="actions">

<button class="primary" onclick="executeTask()">
⚡ EXECUTE TASK
</button>

<button class="secondary" onclick="agentHealth()">
🔍 CHECK AGENT
</button>

</div>

</div>

<div class="card">

<h2>🧠 قدرات التنفيذ</h2>

<div class="capabilities">

<div class="cap">🤖 Bots & AI Agents</div>
<div class="cap">🌐 Websites & Dashboards</div>
<div class="cap">📱 App Interfaces</div>
<div class="cap">📊 Statistics & Reports</div>
<div class="cap">⚖️ Comparisons</div>
<div class="cap">🔧 Bug Fixing</div>
<div class="cap">🗄️ Database Features</div>
<div class="cap">⚙️ Automation</div>
<div class="cap">🚀 Kemet AI Self-Development</div>

</div>

</div>

<div class="card">

<h2>📋 Execution Result</h2>

<pre id="result">Ready.</pre>

</div>

</div>

<script>

const CSRF_TOKEN = "{{ csrf_token }}";

async function agentHealth(){

    const status = document.getElementById("status");

    try{

        const r = await fetch("/admin/bridge/agent-health");

        const data = await r.json();

        if(data.ok){

            status.textContent = "🟢 Termux Agent Online";
            status.className = "status online";

        }else{

            status.textContent = "🔴 Agent Error";
            status.className = "status offline";

        }

    }catch(e){

        status.textContent = "🔴 Agent Offline";
        status.className = "status offline";

    }
}


function copyBridgeResult(){
    const output = document.getElementById("bridge-result-output");

    if(!output){
        return;
    }

    navigator.clipboard.writeText(output.textContent).then(() => {
        const button = document.querySelector('button[onclick="copyBridgeResult()"]');

        if(button){
            const original = button.textContent;
            button.textContent = "✅ تم النسخ";

            setTimeout(() => {
                button.textContent = original;
            }, 1500);
        }
    }).catch(() => {
        alert("تعذر نسخ النتيجة.");
    });
}

async function executeTask(){

    const task =
        document.getElementById("task").value.trim();

    const result =
        document.getElementById("result");

    if(!task){

        result.textContent =
            "اكتب المهمة أولاً.";

        return;
    }

    result.textContent =
        "🧠 Kemet AI يفهم المهمة ويجهز خطة التنفيذ...";

    try{

        const r = await fetch(
            "/admin/bridge/execute",
            {
                method:"POST",

                headers:{
                    "Content-Type":"application/json",
                    "X-CSRFToken":CSRF_TOKEN
                },

                body:JSON.stringify({
                    task:task
                })
            }
        );

        const data = await r.json();

        const output = JSON.stringify(data, null, 2);

        result.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px;">
                <strong>Execution Result</strong>
                <button type="button"
                        onclick="copyBridgeResult()"
                        style="padding:8px 14px;border:1px solid #d1d5db;border-radius:8px;background:#fff;cursor:pointer;">
                    📋 نسخ
                </button>
            </div>
            <pre id="bridge-result-output"
                 style="white-space:pre-wrap;word-break:break-word;margin:0;">${output.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}</pre>
        `;

    }catch(e){

        result.textContent =
            "Execution Error:\\n" + String(e);

    }
}


agentHealth();

</script>

</body>
</html>
"""


@admin_bridge.route("/admin/bridge")
@login_required
@admin_required
def dashboard():
    return render_template_string(
        HTML,
        csrf_token=generate_csrf()
    )


@admin_bridge.route("/admin/bridge/agent-health")
@login_required
@admin_required
def agent_health():

    try:

        data, code = agent_request(
            "GET",
            "/health"
        )

        return jsonify(data), code

    except Exception as exc:

        return jsonify({
            "ok":False,
            "error":str(exc)
        }),503


@admin_bridge.route("/admin/bridge/execute", methods=["POST"])
@login_required
@admin_required
def execute():

    data = request.get_json(silent=True) or {}

    task = str(
        data.get("task") or ""
    ).strip()

    if not task:

        return jsonify({
            "ok":False,
            "error":"task_required"
        }),400

    try:

        plan = build_plan(task)

        approval_requested = bool(data.get("approved", False))
        approver_id = data.get("approver_id")

        result = execute_plan(
            plan,
            approved=approval_requested,
            approver_id=approver_id,
        )

        public_plan = dict(plan)
        public_plan.pop("_write_required", None)

        return jsonify({
            "ok":result.get("ok",False),
            "task":task,
            "plan":public_plan,
            "execution":result
        })

    except Exception as exc:

        return jsonify({
            "ok":False,
            "stage":"execution",
            "error":str(exc)
        }),500


@admin_bridge.route(
    "/admin/bridge/agent-read",
    methods=["POST"]
)
@login_required
@admin_required
def agent_read():

    try:

        data, code = agent_request(
            "POST",
            "/files/read",
            request.get_json(silent=True) or {}
        )

        return jsonify(data), code

    except Exception as exc:

        return jsonify({
            "ok":False,
            "error":str(exc)
        }),503


@admin_bridge.route(
    "/admin/bridge/agent-write",
    methods=["POST"]
)
@login_required
@admin_required
def agent_write():

    try:

        data, code = agent_request(
            "POST",
            "/files/write",
            request.get_json(silent=True) or {}
        )

        return jsonify(data), code

    except Exception as exc:

        return jsonify({
            "ok":False,
            "error":str(exc)
        }),503


@admin_bridge.route(
    "/admin/bridge/agent-search",
    methods=["POST"]
)
@login_required
@admin_required
def agent_search():

    try:

        data, code = agent_request(
            "POST",
            "/search",
            request.get_json(silent=True) or {}
        )

        return jsonify(data), code

    except Exception as exc:

        return jsonify({
            "ok":False,
            "error":str(exc)
        }),503


@admin_bridge.route(
    "/admin/bridge/agent-run",
    methods=["POST"]
)
@login_required
@admin_required
def agent_run():

    try:

        data = request.get_json(silent=True) or {}

        result, code = agent_request(
            "POST",
            "/run",
            {
                "command":data.get("command")
            }
        )

        return jsonify(result), code

    except Exception as exc:

        return jsonify({
            "ok":False,
            "error":str(exc)
        }),503
