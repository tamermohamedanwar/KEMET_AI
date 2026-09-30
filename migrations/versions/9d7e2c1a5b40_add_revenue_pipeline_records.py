"""add governed revenue pipeline records

Revision ID: 9d7e2c1a5b40
Revises: ff91b6e4a320
"""
from alembic import op
import sqlalchemy as sa

revision = "9d7e2c1a5b40"
down_revision = "ff91b6e4a320"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("revenue_pipeline_records"):
        return
    op.create_table(
        "revenue_pipeline_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("pipeline_key", sa.String(length=128), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False, server_default="inquiry"),
        sa.Column("source", sa.String(length=60), nullable=False, server_default="command_center"),
        sa.Column("offer_name", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="EGP"),
        sa.Column("quoted_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("acquisition_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("fulfillment_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("provider_fees", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("refunds", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column("payment_transaction_id", sa.String(length=150), nullable=True),
        sa.Column("fulfillment_reference", sa.String(length=255), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("evidence_digest", sa.String(length=64), nullable=True),
        sa.Column("stage_history", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["demo_leads.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.UniqueConstraint("organization_id", "pipeline_key", name="uq_revenue_pipeline_org_key"),
    )
    for column in ("organization_id", "lead_id", "pipeline_key", "stage", "payment_id", "payment_transaction_id", "evidence_digest", "created_at", "updated_at"):
        op.create_index(f"ix_revenue_pipeline_{column}", "revenue_pipeline_records", [column])


def downgrade():
    op.drop_table("revenue_pipeline_records")
