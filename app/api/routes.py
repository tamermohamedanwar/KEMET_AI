from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from app.models.chat import ChatMessage

api = Blueprint("api", __name__)


@api.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Kemet AI",
        "version": "1.0.0"
    })


@api.route("/api/history", methods=["GET"])
@login_required
def history():

    messages = ChatMessage.query.filter_by(
        user_id=current_user.id
    ).order_by(
        ChatMessage.id.desc()
    ).limit(20).all()

    return jsonify([
        {
            "id": m.id,
            "question": m.question,
            "answer": m.answer,
            "created_at": str(m.created_at)
        }
        for m in messages
    ])

# === KEMET_API_EXECUTION_V1 ===

@api.route("/api/execute", methods=["POST"])
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
