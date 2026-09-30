import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os
import subprocess
import requests

load_dotenv(".env.agent", override=True)


EXECUTION_COMMANDS = {
    "health": ["python", "-c", "print('KEMET_HEALTH_OK')"],
    "test_health": ["python", "-c", "print('KEMET_TEST_HEALTH_OK')"],
    "compile": ["python", "-m", "compileall", "-q", "app", "agent"],
    "git_status": ["git", "status", "--short"],
}

app = Flask(__name__)

TOKEN = os.getenv("KEMET_AGENT_TOKEN", "")
PROJECT = os.path.expanduser("~/products/Kemet_AI")

READ_TOOLS = {
    "list_files": {
        "description": "List files and directories inside Kemet AI",
        "endpoint": "/files/list",
        "properties": {
            "path": {
                "type": "string",
                "description": "Project-relative directory path"
            }
        }
    },
    "read_file": {
        "description": "Read a text file inside Kemet AI",
        "endpoint": "/files/read",
        "properties": {
            "path": {
                "type": "string",
                "description": "Project-relative file path"
            }
        }
    },
    "search_code": {
        "description": "Search source code inside Kemet AI",
        "endpoint": "/search",
        "properties": {
            "query": {
                "type": "string",
                "description": "Text to search for"
            },
            "path": {
                "type": "string",
                "description": "Project-relative path to search"
            }
        }
    }
}

COMMANDS = {
    "health": ["bash", "-c", "echo Kemet AI Bridge is healthy"],
    "test_health": ["curl", "-sS", "http://127.0.0.1:5000/api/health"],
    "compile": [".venv/bin/python", "-m", "compileall", "-q", "app"],
    "git_status": ["git", "status", "--short"],
}
def authorized():
    return (
        bool(TOKEN)
        and request.headers.get("Authorization") == f"Bearer {TOKEN}"
    )

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "Kemet AI ChatGPT Bridge",
        "version": "1.0"
    })


def bridge_proxy(agent_path, payload, timeout=60):
    response = requests.post(
        f"http://127.0.0.1:8765{agent_path}",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )

    try:
        body = response.json()
    except ValueError:
        body = {
            "ok": False,
            "error": "invalid_agent_response",
            "status_code": response.status_code,
            "raw": response.text,
        }

    return jsonify(body), response.status_code


@app.post("/files/list")
def bridge_list_files():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    return bridge_proxy("/files/list", data)


@app.post("/files/read")
def bridge_read_file():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    return bridge_proxy("/files/read", data)


@app.post("/files/write")
def bridge_write_file():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    return bridge_proxy("/files/write", data)


@app.post("/search")
def bridge_search_code():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    return bridge_proxy("/search", data)


@app.get("/commands")
def commands():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    return jsonify({
        "ok": True,
        "commands": sorted(COMMANDS.keys())
    })


@app.post("/agent")
def agent_command():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    return jsonify({
        "ok": False,
        "error": "central_execution_gate_required",
        "message": "Direct execution through this legacy endpoint is disabled. Use the authorized Kemet AI execution path.",
    }), 403

@app.post("/run")
def run_command():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    command = data.get("command")

    if command not in COMMANDS:
        return jsonify({
            "ok": False,
            "error": "command_not_allowed",
            "allowed": sorted(COMMANDS.keys())
        }), 403

    result = subprocess.run(
        COMMANDS[command],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    return jsonify({
        "ok": result.returncode == 0,
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    })




# === KEMET_EXECUTION_BRIDGE_V2 ===

AGENT_URL = "http://127.0.0.1:8765"

def agent_request(method, endpoint, payload=None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.request(
            method,
            AGENT_URL + endpoint,
            headers=headers,
            json=payload or {},
            timeout=120,
        )

        try:
            data = response.json()
        except Exception:
            data = {
                "ok": False,
                "error": "invalid_agent_response",
                "raw": response.text,
            }

        return data, response.status_code

    except Exception as exc:
        return {
            "ok": False,
            "error": "agent_connection_failed",
            "detail": str(exc),
        }, 502


@app.post("/execute")
def execute_agent():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    return jsonify({
        "ok": False,
        "error": "central_execution_gate_required",
        "message": "Direct execution through this legacy endpoint is disabled. Use the authorized Kemet AI execution path.",
    }), 403

@app.post("/execution/plan")
def execution_plan():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    instruction = str(data.get("instruction", "")).strip()

    if not instruction:
        return jsonify({"ok": False, "error": "instruction_required"}), 400

    text = instruction.lower()

    if any(x in text for x in ["health", "status", "check"]):
        command = "health"
    elif any(x in text for x in ["compile", "syntax"]):
        command = "compile"
    elif "git" in text or "changes" in text:
        command = "git_status"
    else:
        command = None

    requires_approval = command not in {"health", "test_health"}

    plan = {
        "type": "execution_plan",
        "status": "waiting_approval" if requires_approval else "ready",
        "command": command,
        "action": command or "review",
        "requires_approval": requires_approval,
        "approved": False,
        "executed": False,
        "external_execution": False,
        "database_mutation": False,
    }

    return jsonify({
        "ok": True,
        "instruction": instruction,
        "plan": plan,
        "approval": {
            "required": requires_approval,
            "status": "waiting_approval" if requires_approval else "not_required",
            "approved": False,
        },
        "execution": {
            "allowed": not requires_approval,
            "executed": False,
        },
    })

@app.post("/execution/approve")
def execution_approve():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    plan = data.get("plan")
    approved = bool(data.get("approved", False))

    # Approval identity must come from the trusted server-side
    # approval context, not from the client request.
    approver_id = data.get("approver_id")

    if approved and approver_id is None:
        return jsonify({
            "ok": False,
            "error": "approver_identity_required",
        }), 403

    if not isinstance(plan, dict):
        return jsonify({
            "ok": False,
            "error": "execution_plan_required",
        }), 403

    if not approved:
        return jsonify({
            "ok": True,
            "status": "waiting_approval",
            "approved": False,
            "plan": plan,
        }), 200

    try:
        from app.core.execution.action_approval_bridge import (
            ActionApprovalBridge,
        )

        bridge = ActionApprovalBridge()
        result = bridge.approve_and_prepare(
            plan=plan,
            approved=True,
            approver_id=approver_id,
        )

        return jsonify({
            "ok": bool(result.get("success")),
            **result,
        }), 200

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": "execution_approval_error",
            "detail": str(exc),
        }), 500


@app.post("/termux/run")
def termux_run():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    operation = str(data.get("operation") or "").strip()
    plan = data.get("plan")
    authorization = data.get("authorization")
    action = str(data.get("action") or "").strip()
    if operation not in {"health", "test_health", "compile", "git_status"}:
        return jsonify({"ok": False, "error": "termux_operation_not_allowed"}), 403
    if action != "termux_engineering":
        return jsonify({"ok": False, "error": "termux_action_binding_invalid"}), 403
    if not isinstance(plan, dict) or not isinstance(authorization, dict) or not action:
        return jsonify({"ok": False, "error": "termux_execution_binding_required"}), 403
    response = requests.post(
        f"{AGENT_URL}/governed/run",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"operation": operation, "plan": plan, "authorization": authorization, "action": action},
        timeout=125,
    )
    try:
        body = response.json()
    except ValueError:
        body = {"ok": False, "error": "invalid_agent_response", "raw": response.text}
    return jsonify(body), response.status_code


@app.post("/termux/artifact")
def termux_artifact():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    artifacts = data.get("artifacts")
    plan = data.get("plan")
    authorization = data.get("authorization")
    action = str(data.get("action") or "").strip()
    preview_digest = str(data.get("preview_digest") or "").strip()
    if action != "artifact_write":
        return jsonify({"ok": False, "error": "artifact_action_binding_invalid"}), 403
    if not isinstance(artifacts, list) or not artifacts:
        return jsonify({"ok": False, "error": "artifact_binding_required"}), 403
    if not isinstance(plan, dict) or not isinstance(authorization, dict):
        return jsonify({"ok": False, "error": "artifact_execution_binding_required"}), 403
    if not preview_digest:
        return jsonify({"ok": False, "error": "artifact_preview_binding_required"}), 403
    return bridge_proxy("/governed/artifact", {
        "artifacts": artifacts, "plan": plan, "authorization": authorization,
        "action": action, "preview_digest": preview_digest,
    }, timeout=130)


@app.post("/execution/run")
def execution_run():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}

    plan = data.get("plan")
    authorization = data.get("authorization")
    action = str(data.get("action") or "").strip()

    if not isinstance(plan, dict):
        return jsonify({
            "ok": False,
            "error": "execution_plan_required",
        }), 403

    if not isinstance(authorization, dict):
        return jsonify({
            "ok": False,
            "error": "execution_authorization_required",
        }), 403

    if not action:
        action = str(plan.get("action") or plan.get("command") or "").strip()

    if not action:
        return jsonify({
            "ok": False,
            "error": "execution_action_required",
        }), 403

    try:
        from app.core.execution.execution_boundary import execution_boundary

        gate_result = execution_boundary.require(
            plan=plan,
            authorization=authorization,
            action=action,
        )

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": "execution_gate_error",
            "detail": str(exc),
        }), 500

    if not gate_result.get("allowed"):
        return jsonify({
            "ok": False,
            "error": gate_result.get("error", "execution_denied"),
            "gate": gate_result,
        }), 403

    command = str(
        plan.get("command")
        or plan.get("action")
        or action
    ).strip()

    if command not in EXECUTION_COMMANDS:
        return jsonify({
            "ok": False,
            "error": "command_not_allowed",
            "allowed": sorted(EXECUTION_COMMANDS.keys()),
        }), 403

    try:
        from app.core.execution.runtime import canonical_execution_runtime
        from app.automation.action_registry import registry

        canonical_plan = dict(plan)
        canonical_plan["action"] = action
        canonical_plan["command"] = command
        canonical_plan["parameters"] = dict(plan.get("parameters") or {})
        canonical_plan["data"] = {
            "engineering_command": command,
            "operation": canonical_plan["parameters"].get("operation"),
        }

        result = canonical_execution_runtime.execute(
            plan=canonical_plan,
            authorization=authorization,
            action_registry=registry,
            user_id=None,
        )

        response = {
            "ok": bool(result.get("success")),
            "command": command,
            "result": result,
            "authorization_consumed": bool(result.get("executed")),
        }

        if not result.get("success") and result.get("error"):
            response["error"] = result["error"]

        return jsonify(response), 200 if result.get("success") else 403

    except Exception as exc:
        return jsonify({
            "ok": False,
            "command": command,
            "error": "canonical_execution_error",
            "detail": str(exc),
        }), 500

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8770,
        debug=False,
    )
