from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from app import db
from app.models.conversation import Conversation
from app.models.chat import ChatMessage


conversations = Blueprint("conversations", __name__)


@conversations.route("/conversations")
@login_required
def list_conversations():
    items = (
        Conversation.query
        .filter(
            Conversation.user_id == current_user.id,
            Conversation.organization_id == current_user.organization_id,
        )
        .order_by(Conversation.updated_at.desc())
        .all()
    )

    return render_template(
        "conversations.html",
        conversations=items
    )


@conversations.route("/conversations/new")
@login_required
def new_conversation():
    conversation = Conversation(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        title="New Chat"
    )

    db.session.add(conversation)
    db.session.commit()

    return redirect(
        url_for(
            "main.chat_page",
            conversation_id=conversation.id
        )
    )


@conversations.route(
    "/conversations/delete/<int:id>",
    methods=["POST"]
)
@login_required
def delete_conversation(id):
    conversation = (
        Conversation.query
        .filter(
            Conversation.id == id,
            Conversation.user_id == current_user.id,
            Conversation.organization_id == current_user.organization_id,
        )
        .first_or_404()
    )

    ChatMessage.query.filter_by(
        conversation_id=conversation.id,
        user_id=current_user.id,
    ).delete()

    db.session.delete(conversation)
    db.session.commit()

    flash("Conversation deleted")

    return redirect(
        url_for("main.chat_page")
    )


@conversations.route(
    "/conversations/rename/<int:id>",
    methods=["POST"]
)
@login_required
def rename_conversation(id):
    conversation = (
        Conversation.query
        .filter(
            Conversation.id == id,
            Conversation.user_id == current_user.id,
            Conversation.organization_id == current_user.organization_id,
        )
        .first_or_404()
    )

    title = request.form.get("title", "").strip()

    if title:
        conversation.title = title[:50]
        db.session.commit()

    return redirect(
        url_for("main.chat_page")
    )
