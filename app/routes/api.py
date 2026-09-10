from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.services.chat_service import ChatService
from app.automation.engine import engine

api = Blueprint("api", __name__)


@api.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Kemet_AI"
    })


@api.route("/ready", methods=["GET"])
def readiness():
    from app.services.production_readiness import production_readiness
    result = production_readiness.check()
    return jsonify(result), 200 if result.get("success") else 503


@api.route("/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json()

    message = data.get("message", "")
    conversation_id = data.get("conversation_id")

    service = ChatService()

    automation_results = engine.execute(
        event="message_received",
        organization_id=current_user.organization_id,
        data={
            "message": message,
            "user_id": current_user.id,
            "conversation_id": conversation_id
        }
    )

    reply, new_conversation_id = service.generate_reply(
        message=message,
        user_id=current_user.id,
        conversation_id=conversation_id
    )

    return jsonify({
        "reply": reply,
        "conversation_id": new_conversation_id
    })


# === KEMET_API_EXECUTION_V1 ===

@api.route("/execute", methods=["POST"])
@login_required
def execute():
    import os
    import requests
    from dotenv import load_dotenv

    load_dotenv(".env.agent", override=False)

    data = request.get_json(silent=True) or {}

    action = str(data.get("action") or "").strip()
    payload = data.get("payload") or {}

    allowed = {
        "health",
        "compile",
        "git_status",
        "test_health",
        "list_files",
        "read_file",
        "search_code",
        "write_file",
    }

    if action not in allowed:
        return jsonify({
            "ok": False,
            "error": "execution_action_not_allowed",
            "allowed": sorted(allowed),
        }), 403

    token = os.getenv("KEMET_AGENT_TOKEN", "")

    if not token:
        return jsonify({
            "ok": False,
            "error": "agent_token_missing",
        }), 503

    try:
        response = requests.post(
            "http://127.0.0.1:8770/execute",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "action": action,
                "payload": payload,
            },
            timeout=120,
        )

        try:
            result = response.json()
        except Exception:
            result = {
                "ok": False,
                "error": "invalid_bridge_response",
                "raw": response.text,
            }

        return jsonify(result), response.status_code

    except requests.RequestException as exc:
        return jsonify({
            "ok": False,
            "error": "bridge_connection_failed",
            "detail": str(exc),
        }), 502

