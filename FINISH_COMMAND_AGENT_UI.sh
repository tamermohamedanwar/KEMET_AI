#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "$HOME/products/Kemet_AI"

echo "===== KEMET AI COMMAND AGENT UI ====="

python - <<'PY'
from pathlib import Path
import os

chat = Path("app/templates/chat.html")
js = Path("app/static/js/kemet-ui.js")

# -------------------------------------------------
# 1. Add Command Agent panel to chat page
# -------------------------------------------------

if chat.exists():
    s = chat.read_text()

    marker = '<!-- KEMET_COMMAND_AGENT -->'

    block = r'''
<!-- KEMET_COMMAND_AGENT -->
<section id="kemet-command-agent" class="kemet-command-agent" style="
    margin:18px 0;
    border:1px solid #e5e7eb;
    border-radius:16px;
    padding:16px;
    background:#fff;
    box-shadow:0 4px 18px rgba(0,0,0,.05);
">
    <div style="font-weight:700;font-size:16px;margin-bottom:10px;">
        🤖 Kemet AI Command Agent
    </div>

    <textarea
        id="kemet-agent-input"
        rows="3"
        placeholder="اكتب ما تريد من Kemet AI أن يبنيه أو ينفذه..."
        style="
            width:100%;
            box-sizing:border-box;
            resize:vertical;
            border:1px solid #d1d5db;
            border-radius:12px;
            padding:12px;
            font:inherit;
        "
    ></textarea>

    <button
        type="button"
        id="kemet-agent-send"
        style="
            margin-top:10px;
            border:0;
            border-radius:10px;
            padding:10px 18px;
            cursor:pointer;
            font-weight:700;
        "
    >
        تنفيذ الطلب
    </button>

    <div id="kemet-agent-result" style="display:none;margin-top:16px;">

        <div style="font-weight:700;margin-bottom:7px;">
            💻 النتيجة البرمجية
        </div>

        <pre id="kemet-agent-code" style="
            white-space:pre-wrap;
            overflow:auto;
            background:#111827;
            color:#f9fafb;
            border-radius:12px;
            padding:14px;
            margin:0;
            max-height:420px;
        "></pre>

        <div style="font-weight:700;margin:16px 0 7px;">
            📝 شرح النتيجة
        </div>

        <div id="kemet-agent-explanation" style="
            border:1px solid #e5e7eb;
            border-radius:12px;
            padding:14px;
            line-height:1.7;
            background:#f9fafb;
        "></div>

    </div>
</section>
'''

    if marker not in s:
        # Put the agent before the composer when possible.
        inserted = False

        for needle in (
            '<div class="composer"',
            '<form',
            '<div class="input-area"',
        ):
            pos = s.find(needle)
            if pos != -1:
                s = s[:pos] + block + "\n" + s[pos:]
                inserted = True
                break

        if not inserted:
            s = s.replace("</body>", block + "\n</body>")

        chat.write_text(s)
        print("CHAT UI: INSTALLED")
    else:
        print("CHAT UI: ALREADY PRESENT")

# -------------------------------------------------
# 2. Add frontend Command Agent behavior
# -------------------------------------------------

if js.exists():
    s = js.read_text()

    marker = "/* KEMET_COMMAND_AGENT */"

    code = r'''
/* KEMET_COMMAND_AGENT */
(function () {
    const input = document.getElementById("kemet-agent-input");
    const send = document.getElementById("kemet-agent-send");
    const result = document.getElementById("kemet-agent-result");
    const codeBox = document.getElementById("kemet-agent-code");
    const explanation = document.getElementById("kemet-agent-explanation");

    if (!input || !send || !result) return;

    function csrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute("content") || "";

        const el = document.querySelector('input[name="csrf_token"]');
        return el ? el.value : "";
    }

    send.addEventListener("click", async function () {
        const instruction = input.value.trim();
        if (!instruction) return;

        send.disabled = true;
        send.textContent = "جارٍ التنفيذ...";

        result.style.display = "block";
        codeBox.textContent = "جاري تنفيذ الطلب...";
        explanation.textContent = "Kemet AI يعمل على تنفيذ طلبك...";

        try {
            const response = await fetch("/api/command-agent", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken()
                },
                body: JSON.stringify({
                    instruction: instruction
                })
            });

            const data = await response.json();

            if (!response.ok || data.ok === false) {
                throw new Error(
                    data.error ||
                    data.message ||
                    "حدث خطأ أثناء تنفيذ الطلب."
                );
            }

            codeBox.textContent =
                data.stdout ||
                data.output ||
                data.result ||
                "تم تنفيذ الطلب بدون مخرجات برمجية.";

            explanation.textContent =
                data.explanation ||
                data.message ||
                "تم استلام وتنفيذ الطلب.";

        } catch (error) {
            codeBox.textContent = String(error.message || error);
            explanation.textContent =
                "تعذر تنفيذ الطلب. راجع نتيجة التنفيذ أعلاه.";
        } finally {
            send.disabled = false;
            send.textContent = "تنفيذ الطلب";
        }
    });
})();
'''

    if marker not in s:
        s += "\n\n" + code + "\n"
        js.write_text(s)
        print("COMMAND AGENT JS: INSTALLED")
    else:
        print("COMMAND AGENT JS: ALREADY PRESENT")

# -------------------------------------------------
# 3. Create backend proxy route
# -------------------------------------------------

route = Path("app/routes/command_agent.py")

route.write_text(r'''
import os
import requests
from flask import Blueprint, jsonify, request
from flask_login import login_required

command_agent_bp = Blueprint(
    "command_agent",
    __name__,
    url_prefix="/api"
)

BRIDGE_URL = os.getenv("KEMET_BRIDGE_URL", "").rstrip("/")
TOKEN = os.getenv("KEMET_AGENT_TOKEN", "")

@command_agent_bp.post("/command-agent")
@login_required
def command_agent():
    data = request.get_json(silent=True) or {}
    instruction = str(data.get("instruction", "")).strip()

    if not instruction:
        return jsonify({
            "ok": False,
            "error": "instruction_required"
        }), 400

    if not BRIDGE_URL or not TOKEN:
        return jsonify({
            "ok": False,
            "error": "command_agent_not_configured"
        }), 503

    try:
        response = requests.post(
            f"{BRIDGE_URL}/agent",
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
            },
            json={"instruction": instruction},
            timeout=120,
        )

        payload = response.json()

        return jsonify(payload), response.status_code

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": "bridge_connection_failed",
            "message": str(exc)
        }), 502
''')

print("BACKEND ROUTE: CREATED")

# -------------------------------------------------
# 4. Register blueprint automatically
# -------------------------------------------------

init = Path("app/__init__.py")

if init.exists():
    s = init.read_text()

    import_line = "from app.routes.command_agent import command_agent_bp"

    if import_line not in s:
        # Insert after other route imports when possible.
        lines = s.splitlines()
        idx = 0

        for i, line in enumerate(lines):
            if "from app.routes" in line:
                idx = i + 1

        lines.insert(idx, import_line)
        s = "\n".join(lines) + ("\n" if s.endswith("\n") else "")

    registration = "app.register_blueprint(command_agent_bp)"

    if registration not in s:
        # Prefer registration near other blueprint registrations.
        lines = s.splitlines()
        idx = len(lines)

        for i, line in enumerate(lines):
            if "register_blueprint" in line:
                idx = i + 1

        lines.insert(idx, registration)
        s = "\n".join(lines) + ("\n" if s.endswith("\n") else "")

    init.write_text(s)
    print("BLUEPRINT: REGISTERED")

# -------------------------------------------------
# 5. Configure Bridge URL without exposing token
# -------------------------------------------------

env = Path(".env")

if env.exists():
    s = env.read_text()

    tunnel = os.environ.get("TUNNEL_URL", "").strip()

    if tunnel and "KEMET_BRIDGE_URL=" not in s:
        with env.open("a") as f:
            f.write("\nKEMET_BRIDGE_URL=" + tunnel + "\n")
        print("BRIDGE URL: CONFIGURED FROM TUNNEL_URL")
    else:
        print("BRIDGE URL: PRESERVED")

print("======================================")
print(" KEMET COMMAND AGENT UI READY")
print("======================================")
PY

echo
echo "===== RESTART APPLICATION ====="

pkill -f 'gunicorn.*wsgi:application' 2>/dev/null || true
sleep 2

if [ -x ".venv/bin/gunicorn" ]; then
    nohup .venv/bin/gunicorn \
        -c gunicorn.conf.py \
        wsgi:application \
        > runtime_logs/gunicorn.log 2>&1 &
else
    nohup .venv/bin/python -m gunicorn \
        -c gunicorn.conf.py \
        wsgi:application \
        > runtime_logs/gunicorn.log 2>&1 &
fi

echo
echo "======================================"
echo " KEMET AI COMMAND AGENT INSTALLED"
echo "======================================"
echo
echo "Inside the Kemet AI page you now have:"
echo
echo "🤖 Command Agent"
echo "💻 Programming Result"
echo "📝 Result Explanation"
echo
echo "MCP: NOT USED"
echo "Copy/Paste: NOT REQUIRED"
echo
