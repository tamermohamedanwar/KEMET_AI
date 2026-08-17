from datetime import datetime

from app import db


class TicketReply(db.Model):
    __tablename__ = "ticket_replies"

    id = db.Column(db.Integer, primary_key=True)

    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("tickets.id"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    source_message = db.Column(
        db.Text,
        nullable=True
    )

    is_staff = db.Column(
        db.Boolean,
        default=False
    )

    is_ai = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
