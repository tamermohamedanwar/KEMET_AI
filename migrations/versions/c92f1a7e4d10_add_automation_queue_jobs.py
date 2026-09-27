"""add durable automation queue jobs

Revision ID: c92f1a7e4d10
Revises: b71d4a8c91ef
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "c92f1a7e4d10"
down_revision = "b71d4a8c91ef"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("automation_queue_jobs"):
        return
    bind = op.get_bind()
    if sa.inspect(bind).has_table("automation_queue_jobs"):
        return
    op.create_table(
        "automation_queue_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("job_key", sa.String(length=255), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=True),
        sa.Column("trigger_id", sa.String(length=255), nullable=True),
        sa.Column("workflow_id", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("organization_id", "job_key", name="uq_automation_queue_org_job"),
    )
    for name, columns in (
        ("ix_automation_queue_jobs_organization_id", ["organization_id"]),
        ("ix_automation_queue_jobs_job_key", ["job_key"]),
        ("ix_automation_queue_jobs_event_id", ["event_id"]),
        ("ix_automation_queue_jobs_trigger_id", ["trigger_id"]),
        ("ix_automation_queue_jobs_workflow_id", ["workflow_id"]),
        ("ix_automation_queue_jobs_status", ["status"]),
        ("ix_automation_queue_jobs_priority", ["priority"]),
        ("ix_automation_queue_jobs_available_at", ["available_at"]),
        ("ix_automation_queue_jobs_correlation_id", ["correlation_id"]),
        ("ix_automation_queue_jobs_trace_id", ["trace_id"]),
    ):
        op.create_index(name, "automation_queue_jobs", columns, unique=False)


def downgrade():
    for name in (
        "ix_automation_queue_jobs_trace_id", "ix_automation_queue_jobs_correlation_id",
        "ix_automation_queue_jobs_available_at", "ix_automation_queue_jobs_priority",
        "ix_automation_queue_jobs_status", "ix_automation_queue_jobs_workflow_id",
        "ix_automation_queue_jobs_trigger_id", "ix_automation_queue_jobs_event_id",
        "ix_automation_queue_jobs_job_key", "ix_automation_queue_jobs_organization_id",
    ):
        op.drop_index(name, table_name="automation_queue_jobs")
    op.drop_table("automation_queue_jobs")
