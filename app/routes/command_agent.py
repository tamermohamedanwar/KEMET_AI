
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
