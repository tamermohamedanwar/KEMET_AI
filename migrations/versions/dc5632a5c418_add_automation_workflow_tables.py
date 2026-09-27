"""add automation workflow tables

Revision ID: dc5632a5c418
Revises: 7f4e9b2c1d11
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "dc5632a5c418"
down_revision = "7f4e9b2c1d11"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("automation_workflows") and inspector.has_table("automation_actions") and inspector.has_table("automation_executions"):
        return
    op.create_table(
        "automation_workflows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "trigger_type",
            sa.String(length=50),
            nullable=False,
            server_default="ticket_created",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_automation_workflows_organization_id",
        "automation_workflows",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "automation_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["automation_workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_automation_actions_workflow_id",
        "automation_actions",
        ["workflow_id"],
        unique=False,
    )

    op.create_table(
        "automation_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="running",
        ),
        sa.Column("input_json", sa.Text(), nullable=True),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["automation_workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_automation_executions_workflow_id",
        "automation_executions",
        ["workflow_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_automation_executions_workflow_id",
        table_name="automation_executions",
    )
    op.drop_table("automation_executions")

    op.drop_index(
        "ix_automation_actions_workflow_id",
        table_name="automation_actions",
    )
    op.drop_table("automation_actions")

    op.drop_index(
        "ix_automation_workflows_organization_id",
        table_name="automation_workflows",
    )
    op.drop_table("automation_workflows")
