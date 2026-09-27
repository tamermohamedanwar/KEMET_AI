from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

from app.services.chat_service import ChatService

chat = Blueprint("chat", __name__)

service = ChatService()


@chat.route("/api/chat", methods=["POST"])
@login_required
def chat_api():
    data = request.get_json(silent=True) or {}

    message = data.get("message", "")
    conversation_id = data.get("conversation_id")

    reply, conversation_id = service.generate_reply(
        message=message,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        conversation_id=conversation_id,
    )

    return jsonify({
        "reply": reply,
        "conversation_id": conversation_id,
    })
