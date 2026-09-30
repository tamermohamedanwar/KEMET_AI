"""add canonical commercial offers

Revision ID: c9e4f2a7b610
Revises: b1c2d3e4f506
"""

from alembic import op
import sqlalchemy as sa

revision = "c9e4f2a7b610"
down_revision = "b1c2d3e4f506"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commercial_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("pipeline_id", sa.Integer(), nullable=False),
        sa.Column("offer_name", sa.String(length=255), nullable=False),
        sa.Column("offer_description", sa.Text(), nullable=False),
        sa.Column("quoted_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="EGP"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("evidence_provenance", sa.JSON(), nullable=False),
        sa.Column("approval_package_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["demo_leads.id"]),
        sa.ForeignKeyConstraint(["pipeline_id"], ["revenue_pipeline_records.id"]),
        sa.UniqueConstraint("organization_id", "pipeline_id", name="uq_commercial_offer_org_pipeline"),
    )


def downgrade():
    op.drop_table("commercial_offers")
