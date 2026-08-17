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
