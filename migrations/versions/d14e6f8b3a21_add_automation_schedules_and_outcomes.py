"""add durable automation schedules and outcome telemetry

Revision ID: d14e6f8b3a21
Revises: c92f1a7e4d10
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "d14e6f8b3a21"
down_revision = "c92f1a7e4d10"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("automation_schedules") and inspector.has_table("automation_outcomes"):
        return
    op.create_table(
        "automation_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("schedule_key", sa.String(length=255), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False, server_default="UTC"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("organization_id", "schedule_key", name="uq_automation_schedule_org_key"),
    )
    op.create_index("ix_automation_schedules_organization_id", "automation_schedules", ["organization_id"])
    op.create_index("ix_automation_schedules_workflow_id", "automation_schedules", ["workflow_id"])
    op.create_index("ix_automation_schedules_enabled", "automation_schedules", ["enabled"])
    op.create_index("ix_automation_schedules_next_run_at", "automation_schedules", ["next_run_at"])
    op.create_table(
        "automation_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("workflow_id", sa.String(length=255), nullable=True),
        sa.Column("event_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("business_outcome", sa.String(length=100), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("receipt_json", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["automation_queue_jobs.id"]),
    )
