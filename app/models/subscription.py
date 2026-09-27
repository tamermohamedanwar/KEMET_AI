from app import db

class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        nullable=False,
        unique=True
    )

    plan = db.Column(
        db.String(30),
        nullable=False,
        default="free"
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="active"
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )

    __table_args__ = (db.Index("ix_subscriptions_org_status", "organization_id", "status"),)
