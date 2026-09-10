"""add durable execution evidence history

Revision ID: a8c5d7e2f310
Revises: f2a6c8d9e410
"""
from alembic import op
import sqlalchemy as sa

revision = "a8c5d7e2f310"
down_revision = "f2a6c8d9e410"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "execution_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("execution_key", sa.String(length=512), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.String(length=255), nullable=True),
        sa.Column("workflow_id", sa.String(length=255), nullable=True),
        sa.Column("stage", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("plan_hash", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("evidence_key", sa.String(length=512), nullable=False),
        sa.Column("receipt_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["automation_queue_jobs.id"]),
        sa.UniqueConstraint("organization_id", "evidence_key", name="uq_execution_evidence_org_key"),
    )
    for column in (
        "organization_id", "execution_key", "job_id", "event_id", "workflow_id",
        "stage", "status", "worker_id", "plan_hash", "correlation_id", "trace_id",
        "evidence_key", "created_at",
    ):
        op.create_index(f"ix_execution_evidence_{column}", "execution_evidence", [column])


def downgrade():
    op.drop_table("execution_evidence")
