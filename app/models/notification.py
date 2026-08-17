from datetime import datetime

from app import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    title = db.Column(
        db.String(255),
        nullable=False,
    )

    message = db.Column(
        db.Text,
        nullable=False,
    )

    channel = db.Column(
        db.String(50),
        nullable=False,
        default="internal",
    )

    status = db.Column(
        db.String(50),
        nullable=False,
        default="sent",
    )

    is_read = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    read_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    def __repr__(self):
        return (
            f"<Notification id={self.id} "
            f"organization_id={self.organization_id} "
            f"status={self.status}>"
        )
