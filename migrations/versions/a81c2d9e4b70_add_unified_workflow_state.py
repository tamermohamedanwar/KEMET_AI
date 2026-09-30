"""add unified workflow state to durable queue jobs

Revision ID: a81c2d9e4b70
Revises: f7a9c3e1b602
"""
from alembic import op
import sqlalchemy as sa

revision = "a81c2d9e4b70"
down_revision = "f7a9c3e1b602"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("automation_queue_jobs")}
    if "execution_id" not in columns:
        op.add_column("automation_queue_jobs", sa.Column("execution_id", sa.String(length=255), nullable=True))
    if "idempotency_key" not in columns:
        op.add_column("automation_queue_jobs", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    if "workflow_state" not in columns:
        op.add_column("automation_queue_jobs", sa.Column("workflow_state", sa.String(length=40), nullable=False, server_default="queued"))
    if "state_version" not in columns:
        op.add_column("automation_queue_jobs", sa.Column("state_version", sa.Integer(), nullable=False, server_default="0"))
    if "state_reason" not in columns:
        op.add_column("automation_queue_jobs", sa.Column("state_reason", sa.String(length=500), nullable=True))
    if "state_updated_at" not in columns:
        op.add_column("automation_queue_jobs", sa.Column("state_updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_automation_queue_jobs_execution_id", "automation_queue_jobs", ["execution_id"], unique=False)
    op.create_index("ix_automation_queue_jobs_idempotency_key", "automation_queue_jobs", ["idempotency_key"], unique=False)
    op.create_index("ix_automation_queue_jobs_workflow_state", "automation_queue_jobs", ["workflow_state"], unique=False)


def downgrade():
    for name in ("ix_automation_queue_jobs_workflow_state", "ix_automation_queue_jobs_idempotency_key", "ix_automation_queue_jobs_execution_id"):
        op.drop_index(name, table_name="automation_queue_jobs")
    for name in ("state_updated_at", "state_reason", "state_version", "workflow_state", "idempotency_key", "execution_id"):
        op.drop_column("automation_queue_jobs", name)
