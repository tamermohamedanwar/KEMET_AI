from app import db


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)

    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("conversations.id"),
        nullable=True,
        index=True,
    )

    user_id = db.Column(db.Integer, nullable=True)

    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
    )

