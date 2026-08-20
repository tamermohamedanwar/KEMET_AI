"""add lead activities crm v2

Revision ID: c0489dc4f8ca
Revises: 502a0d2d6d72
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "c0489dc4f8ca"
down_revision = "502a0d2d6d72"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lead_activities",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.Integer(),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "lead_id",
            sa.Integer(),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "activity_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column(
            "subject",
            sa.String(255),
            nullable=True,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "old_status",
            sa.String(30),
            nullable=True,
        ),
        sa.Column(
            "new_status",
            sa.String(30),
            nullable=True,
        ),
        sa.Column(
            "scheduled_at",
            sa.DateTime(),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_lead_activities_organization",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["demo_leads.id"],
            name="fk_lead_activities_lead",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_lead_activities_user",
        ),
    )


def downgrade():
    op.drop_table("lead_activities")
