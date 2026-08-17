from app import db


class DemoLead(db.Model):
    __tablename__ = "demo_leads"

    id = db.Column(db.Integer, primary_key=True)

    company_name = db.Column(
        db.String(150),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=True
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="new"
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )
