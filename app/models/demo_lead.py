from app import db


class DemoLead(db.Model):
    __tablename__ = "demo_leads"

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

    company_name = db.Column(
        db.String(150),
        nullable=False,
    )

    email = db.Column(
        db.String(150),
        nullable=False,
        index=True,
    )

    phone = db.Column(
        db.String(50),
        nullable=True,
    )

    message = db.Column(
        db.Text,
        nullable=True,
    )

    source = db.Column(
        db.String(50),
        nullable=False,
        default="website",
        index=True,
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="new",
        index=True,
    )

    lead_score = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    estimated_value = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0,
    )

    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    notes = db.Column(
        db.Text,
        nullable=True,
    )

    last_contact_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    next_follow_up_at = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
    )

    converted_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    lost_reason = db.Column(
        db.String(255),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        nullable=False,
    )

    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )
