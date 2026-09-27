"""add durable execution ledger

Revision ID: e7f4a9c2d610
Revises: d4e7a1c9f210
"""
from alembic import op
import sqlalchemy as sa

revision = "e7f4a9c2d610"
down_revision = "d4e7a1c9f210"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("automation_execution_ledger"):
        return
    bind = op.get_bind()
    if sa.inspect(bind).has_table("automation_execution_ledger"):
        return
    op.create_table(
        "automation_execution_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("execution_key", sa.String(length=512), nullable=False),
        sa.Column("plan_hash", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("approval_hash", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        sa.Column("receipt_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "execution_key", name="uq_execution_ledger_org_key"),
    )
    for column in ("organization_id", "execution_key", "plan_hash", "job_id", "worker_id", "status", "approval_hash", "trace_id", "correlation_id", "created_at"):
        op.create_index(f"ix_execution_ledger_{column}", "automation_execution_ledger", [column])


def downgrade():
    op.drop_table("automation_execution_ledger")
