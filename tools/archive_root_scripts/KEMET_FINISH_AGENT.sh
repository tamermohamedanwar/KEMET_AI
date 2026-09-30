#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "$HOME/products/Kemet_AI"

TOKEN="$(grep '^KEMET_AGENT_TOKEN=' .env | head -1 | cut -d= -f2-)"
export KEMET_AGENT_TOKEN="$TOKEN"

echo "===== KEMET AI — FINISH COMMAND AGENT ====="

python - <<'PY'
from pathlib import Path

p = Path("agent/chatgpt_bridge.py")
s = p.read_text()

if '@app.post("/agent")' not in s:
    marker = '@app.post("/run")'
    insert = r'''
@app.post("/agent")
def agent_command():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    instruction = str(data.get("instruction", "")).strip()

    if not instruction:
        return jsonify({
            "ok": False,
            "error": "instruction_required"
        }), 400

    text = instruction.lower()

    aliases = {
        "health": "health",
        "اختبر": "health",
        "فحص": "health",
        "compile": "compile",
        "ترجمة": "compile",
        "compileall": "compile",
        "git": "git_status",
        "git status": "git_status",
        "حالة git": "git_status",
        "حالة المشروع": "git_status",
    }

    command = None
    for key, value in aliases.items():
        if key in text:
            command = value
            break

    if command:
        result = subprocess.run(
            COMMANDS[command],
            cwd=PROJECT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        return jsonify({
            "ok": result.returncode == 0,
            "instruction": instruction,
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        })

    return jsonify({
        "ok": True,
        "instruction": instruction,
        "status": "received",
        "message": "Instruction received by Kemet AI Bridge. The page can now pass an AI-generated execution plan to /run."
    })
'''
    s = s.replace(marker, insert + "\n" + marker)
    p.write_text(s)

print("AGENT ENDPOINT INSTALLED")
PY

echo "Restarting Bridge..."

pkill -f 'python agent/chatgpt_bridge.py' 2>/dev/null || true
sleep 2

nohup env KEMET_AGENT_TOKEN="$KEMET_AGENT_TOKEN" \
  .venv/bin/python agent/chatgpt_bridge.py \
  > runtime_logs/bridge.log 2>&1 &

echo $! > runtime_logs/bridge.pid

echo
echo "======================================"
echo " KEMET AI COMMAND AGENT READY"
echo "======================================"
echo
echo "Natural language endpoint:"
echo "POST $TUNNEL_URL/agent"
echo
echo "Execution endpoint:"
echo "POST $TUNNEL_URL/run"
echo
echo "The next UI layer can now send:"
echo "instruction -> AI planner -> /run -> Termux"
echo
