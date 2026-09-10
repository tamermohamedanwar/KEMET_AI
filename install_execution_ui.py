from pathlib import Path
import shutil
from datetime import datetime

ROOT = Path.home() / "products" / "Kemet_AI"
APP = ROOT / "app"
ROUTES = APP / "routes"
TEMPLATES = APP / "templates"

BACKUP = ROOT / "KEMET_AI_BUILD_BACKUPS" / (
    "execution_ui_" + datetime.now().strftime("%Y%m%d_%H%M%S")
)

ROUTES.mkdir(parents=True, exist_ok=True)
TEMPLATES.mkdir(parents=True, exist_ok=True)
BACKUP.mkdir(parents=True, exist_ok=True)

route = ROUTES / "execution_center.py"

route_code = r'''
import os
from pathlib import Path

import requests
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

execution_bp = Blueprint("execution_center", __name__)

BRIDGE_URL = os.getenv(
    "KEMET_BRIDGE_URL",
    "http://127.0.0.1:8770"
)

def load_token():
    token = os.getenv("KEMET_AGENT_TOKEN", "").strip()

    if token:
        return token

    env_file = (
        Path.home()
        / "products"
        / "Kemet_AI"
        / ".env.agent"
    )

    if env_file.exists():
        for line in env_file.read_text(
            errors="ignore"
        ).splitlines():

            line = line.strip()

            if line.startswith("KEMET_AGENT_TOKEN="):
                return (
                    line.split("=", 1)[1]
                    .strip()
                    .strip('"')
                    .strip("'")
                )

    return ""

def bridge_headers():
    return {
        "Authorization": f"Bearer {load_token()}",
        "Content-Type": "application/json",
    }

@execution_bp.get("/execution-center")
@login_required
def execution_center():
    return render_template("execution_center.html")

@execution_bp.post("/api/execution/plan")
@login_required
def execution_plan():

    data = request.get_json(silent=True) or {}

    instruction = str(
        data.get("instruction", "")
    ).strip()

    if not instruction:
        return jsonify({
            "ok": False,
            "error": "instruction_required"
        }), 400

    try:
        response = requests.post(
            f"{BRIDGE_URL}/execution/plan",
            headers=bridge_headers(),
            json={"instruction": instruction},
            timeout=20,
        )

        return jsonify(response.json()), response.status_code

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc)
        }), 502

@execution_bp.post("/api/execution/run")
@login_required
def execution_run():

    data = request.get_json(silent=True) or {}

    command = str(
        data.get("command", "")
    ).strip()

    approved = bool(
        data.get("approved", False)
    )

    allowed = {
        "health",
        "test_health",
        "compile",
        "git_status",
    }

    safe = {
        "health",
        "test_health",
    }

    if command not in allowed:
        return jsonify({
            "ok": False,
            "error": "command_not_allowed"
        }), 400

    if command not in safe and not approved:
        return jsonify({
            "ok": False,
            "error": "approval_required",
            "command": command
        }), 403

    try:
        response = requests.post(
            f"{BRIDGE_URL}/execution/run",
            headers=bridge_headers(),
            json={"command": command},
            timeout=130,
        )

        return jsonify(response.json()), response.status_code

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc)
        }), 502
'''

route.write_text(route_code, encoding="utf-8")

template = TEMPLATES / "execution_center.html"

template_code = r'''
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport"
content="width=device-width,initial-scale=1">

<title>KEMET AI - Execution Center</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f7f8fa;
    color: #15171a;
}

.wrap {
    max-width: 1000px;
    margin: auto;
    padding: 32px 20px;
}

.card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 8px 30px rgba(0,0,0,.05);
}

h1 {
    margin: 0 0 8px;
}

.sub {
    color: #6b7280;
    margin-bottom: 24px;
}

textarea {
    width: 100%;
    min-height: 130px;
    resize: vertical;
    border: 1px solid #d1d5db;
    border-radius: 12px;
    padding: 14px;
    font-size: 16px;
}

button {
    border: 0;
    border-radius: 10px;
    padding: 12px 18px;
    margin-top: 14px;
    cursor: pointer;
    font-weight: 700;
}

.primary {
    background: #111827;
    color: white;
}

.approve {
    background: #16a34a;
    color: white;
}

pre {
    background: #111827;
    color: #e5e7eb;
    border-radius: 12px;
    padding: 16px;
    overflow: auto;
    min-height: 100px;
}

.plan {
    margin-top: 22px;
    display: none;
}

.status {
    margin-top: 14px;
    font-weight: 700;
}
</style>
</head>

<body>

<div class="wrap">

<div class="card">

<h1>KEMET AI - Execution Center</h1>

<div class="sub">
Send an instruction to Kemet AI.
The system creates an execution plan
and runs only approved commands.
</div>

<textarea
id="instruction"
placeholder="Example: check Kemet AI health">
</textarea>

<br>

<button
class="primary"
onclick="createPlan()">
Create Execution Plan
</button>

<div
id="status"
class="status">
</div>

<div
id="plan"
class="plan">

<h3>Execution Plan</h3>

<pre id="planOutput"></pre>

<button
id="runButton"
class="approve"
onclick="runCommand()">
Approve and Run
</button>

</div>

<div style="margin-top:24px">

<h3>Execution Result</h3>

<pre id="result">
Waiting for execution...
</pre>

</div>

</div>

</div>

<script>

let currentCommand = null;

async function createPlan() {

    const instruction =
        document
        .getElementById("instruction")
        .value
        .trim();

    if (!instruction) {
        return;
    }

    setStatus("Creating execution plan...");

    const response = await fetch(
        "/api/execution/plan",
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                instruction: instruction
            })
        }
    );

    const data = await response.json();

    document
        .getElementById("planOutput")
        .textContent =
        JSON.stringify(data, null, 2);

    document
        .getElementById("plan")
        .style.display = "block";

    if (!data.ok) {

        setStatus(
            "Plan failed: " +
            (data.error || "unknown error")
        );

        return;
    }

    currentCommand =
        data.plan.command;

    const button =
        document.getElementById("runButton");

    if (!currentCommand) {

        button.disabled = true;

        setStatus(
            "No supported command found."
        );

        return;
    }

    button.disabled = false;

    if (data.plan.requires_approval) {

        button.textContent =
            "Approve and Run";

        setStatus(
            "Approval required before execution."
        );

    } else {

        button.textContent = "Run";

        setStatus(
            "Safe command ready."
        );
    }
}

async function runCommand() {

    if (!currentCommand) {
        return;
    }

    setStatus("Executing...");

    const response = await fetch(
        "/api/execution/run",
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                command: currentCommand,
                approved: true
            })
        }
    );

    const data = await response.json();

    document
        .getElementById("result")
        .textContent =
        JSON.stringify(data, null, 2);

    if (data.ok) {

        setStatus(
            "Execution completed successfully."
        );

    } else {

        setStatus(
            "Execution failed."
        );
    }
}

function setStatus(text) {

    document
        .getElementById("status")
        .textContent = text;
}

</script>

</body>
</html>
'''

template.write_text(
    template_code,
    encoding="utf-8"
)

init = APP / "__init__.py"

if not init.exists():
    raise SystemExit("ERROR: app/__init__.py not found")

shutil.copy2(
    init,
    BACKUP / "__init__.py"
)

text = init.read_text(encoding="utf-8")

import_line = (
    "from app.routes.execution_center "
    "import execution_bp"
)

if import_line not in text:

    lines = text.splitlines()

    index = 0

    for i, line in enumerate(lines):

        if (
            line.startswith("import ")
            or line.startswith("from ")
        ):
            index = i + 1

    lines.insert(index, import_line)

    text = "\n".join(lines) + "\n"

registration = "app.register_blueprint(execution_bp)"

if registration not in text:

    lines = text.splitlines()

    found = False

    for i, line in enumerate(lines):

        if line.startswith("def create_app"):

            j = i + 1

            while j < len(lines):

                if (
                    lines[j].strip()
                    and not lines[j].startswith(
                        (" ", "\t")
                    )
                ):
                    break

                j += 1

            lines.insert(
                j,
                "    " + registration
            )

            found = True
            break

    if not found:
        raise SystemExit(
            "ERROR: create_app not found"
        )

    text = "\n".join(lines) + "\n"

init.write_text(
    text,
    encoding="utf-8"
)

print("EXECUTION_UI: INSTALLED")
print("ROUTE: /execution-center")
print("API: /api/execution/plan")
print("API: /api/execution/run")
print("BACKUP:", BACKUP)
