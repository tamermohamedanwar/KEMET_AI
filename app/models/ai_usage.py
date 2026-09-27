from app import db


class AIUsage(db.Model):
    __tablename__ = "ai_usage"

    id = db.Column(db.Integer, primary_key=True)

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        nullable=False,
        index=True
    )

    month = db.Column(
        db.String(7),
        nullable=False,
        index=True
    )

    requests = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    tokens = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )

    __table_args__ = (db.Index("ix_ai_usage_org_created", "organization_id", "created_at"),)
