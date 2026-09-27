from app import db
from datetime import datetime


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        index=True,
        nullable=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    status = db.Column(
        db.String(50),
        default="open",
        nullable=False
    )

    priority = db.Column(
        db.String(20),
        default="medium",
        nullable=False
    )

    assigned_to_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    message_hash = db.Column(
        db.String(64),
        nullable=True,
        index=True
    )

    assigned_to = db.relationship(
        "User",
        foreign_keys=[assigned_to_id]
    )

    replies = db.relationship(
        "TicketReply",
        backref="ticket",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="TicketReply.created_at"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    __table_args__ = (db.Index("ix_tickets_org_created_status", "organization_id", "created_at", "status"),)

    def __repr__(self):
        return f"<Ticket {self.id}>"
