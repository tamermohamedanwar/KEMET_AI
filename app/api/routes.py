from flask import Blueprint, jsonify
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
