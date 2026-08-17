"""add payments table

Revision ID: 1c1e9ae8281a
Revises: 03c92cc692f5
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa


revision = "1c1e9ae8281a"
down_revision = "03c92cc692f5"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "payments" not in inspector.get_table_names():
        op.create_table(
            "payments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "plan",
                sa.String(length=30),
                nullable=False,
            ),
            sa.Column(
                "amount",
                sa.Numeric(precision=10, scale=2),
                nullable=False,
            ),
            sa.Column(
                "currency",
                sa.String(length=10),
                nullable=False,
                server_default="USD",
            ),
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "provider",
                sa.String(length=30),
                nullable=False,
                server_default="paymob",
            ),
            sa.Column(
                "provider_transaction_id",
                sa.String(length=150),
                nullable=True,
            ),
            sa.Column(
                "provider_order_id",
                sa.String(length=150),
                nullable=True,
            ),
            sa.Column(
                "checkout_id",
                sa.String(length=150),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organizations.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "provider_transaction_id",
                name="uq_payments_provider_transaction_id",
            ),
        )

    existing_indexes = {
        index["name"]
        for index in inspector.get_indexes("payments")
    } if "payments" in inspector.get_table_names() else set()

    if "ix_payments_organization_id" not in existing_indexes:
        op.create_index(
            "ix_payments_organization_id",
            "payments",
            ["organization_id"],
        )

    if "ix_payments_status" not in existing_indexes:
        op.create_index(
            "ix_payments_status",
            "payments",
            ["status"],
        )

    if "ix_payments_provider_transaction_id" not in existing_indexes:
        op.create_index(
            "ix_payments_provider_transaction_id",
            "payments",
            ["provider_transaction_id"],
            unique=True,
        )

    if "ix_payments_provider_order_id" not in existing_indexes:
        op.create_index(
            "ix_payments_provider_order_id",
            "payments",
            ["provider_order_id"],
        )

    if "ix_payments_checkout_id" not in existing_indexes:
        op.create_index(
            "ix_payments_checkout_id",
            "payments",
            ["checkout_id"],
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "payments" not in inspector.get_table_names():
        return

    existing_indexes = {
        index["name"]
        for index in inspector.get_indexes("payments")
    }

    for index_name in [
        "ix_payments_checkout_id",
        "ix_payments_provider_order_id",
        "ix_payments_provider_transaction_id",
        "ix_payments_status",
        "ix_payments_organization_id",
    ]:
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="payments")

    op.drop_table("payments")
