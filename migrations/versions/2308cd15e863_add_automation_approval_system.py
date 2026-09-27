"""add automation approval system

Revision ID: 2308cd15e863
Revises:
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa


revision = "2308cd15e863"
down_revision = "2147ec12a0eb"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("automation_approvals"):
        return
    op.create_table(
        "automation_approvals",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "organization_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "workflow_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "execution_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "action_type",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),

        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "request_json",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "decision_json",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "requested_by",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "decided_by",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),

        sa.Column(
            "decided_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_automation_approvals_organization",
        ),

        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["automation_workflows.id"],
            name="fk_automation_approvals_workflow",
        ),

        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["automation_executions.id"],
            name="fk_automation_approvals_execution",
        ),

        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_automation_approvals_requested_by",
        ),

        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name="fk_automation_approvals_decided_by",
        ),
    )

    op.create_index(
        "ix_automation_approvals_organization_id",
        "automation_approvals",
        ["organization_id"],
    )

    op.create_index(
        "ix_automation_approvals_workflow_id",
        "automation_approvals",
        ["workflow_id"],
    )

    op.create_index(
        "ix_automation_approvals_execution_id",
        "automation_approvals",
        ["execution_id"],
    )

    op.create_index(
        "ix_automation_approvals_status",
        "automation_approvals",
        ["status"],
    )


def downgrade():
    op.drop_index(
        "ix_automation_approvals_status",
        table_name="automation_approvals",
    )

    op.drop_index(
        "ix_automation_approvals_execution_id",
        table_name="automation_approvals",
    )

    op.drop_index(
        "ix_automation_approvals_workflow_id",
        table_name="automation_approvals",
    )

    op.drop_index(
        "ix_automation_approvals_organization_id",
        table_name="automation_approvals",
    )

    op.drop_table("automation_approvals")
