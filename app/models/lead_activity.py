from app import db


class LeadActivity(db.Model):
    __tablename__ = "lead_activities"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    lead_id = db.Column(
        db.Integer,
        db.ForeignKey("demo_leads.id"),
        nullable=False,
        index=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    activity_type = db.Column(
        db.String(30),
        nullable=False,
        default="note",
        index=True,
    )

    subject = db.Column(
        db.String(255),
        nullable=True,
    )

    content = db.Column(
        db.Text,
        nullable=True,
    )

    due_at = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        nullable=False,
        index=True,
    )
