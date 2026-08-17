from app import db


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    plan = db.Column(
        db.String(30),
        nullable=False,
    )

    amount = db.Column(
        db.Numeric(10, 2),
        nullable=False,
    )

    currency = db.Column(
        db.String(10),
        nullable=False,
        default="USD",
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="pending",
        index=True,
    )

    provider = db.Column(
        db.String(30),
        nullable=False,
        default="paymob",
    )

    provider_transaction_id = db.Column(
        db.String(150),
        nullable=True,
        unique=True,
        index=True,
    )

    provider_order_id = db.Column(
        db.String(150),
        nullable=True,
        index=True,
    )

    checkout_id = db.Column(
        db.String(150),
        nullable=True,
        index=True,
    )

    client_secret = db.Column(
        db.String(1000),
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
