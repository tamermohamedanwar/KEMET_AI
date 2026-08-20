"""add organization_id to demo leads

Revision ID: 305e30b25782
Revises: 2308cd15e863
"""

from alembic import op
import sqlalchemy as sa


revision = "305e30b25782"
down_revision = "2308cd15e863"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("demo_leads", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("organization_id", sa.Integer(), nullable=True)
        )
        batch_op.create_index(
            "ix_demo_leads_organization_id",
            ["organization_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_demo_leads_organization_id",
            "organizations",
            ["organization_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("demo_leads", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_demo_leads_organization_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_demo_leads_organization_id")
        batch_op.drop_column("organization_id")
