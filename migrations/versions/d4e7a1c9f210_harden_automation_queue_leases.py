"""harden automation queue leases and execution deadlines

Revision ID: d4e7a1c9f210
Revises: c92f1a7e4d10
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e7a1c9f210"
down_revision = "c92f1a7e4d10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("automation_queue_jobs", sa.Column("lease_owner", sa.String(length=255), nullable=True))
    op.add_column("automation_queue_jobs", sa.Column("deadline_at", sa.DateTime(), nullable=True))
    op.create_index("ix_automation_queue_jobs_lease_owner", "automation_queue_jobs", ["lease_owner"], unique=False)
    op.create_index("ix_automation_queue_jobs_deadline_at", "automation_queue_jobs", ["deadline_at"], unique=False)


def downgrade():
    op.drop_index("ix_automation_queue_jobs_deadline_at", table_name="automation_queue_jobs")
    op.drop_index("ix_automation_queue_jobs_lease_owner", table_name="automation_queue_jobs")
    op.drop_column("automation_queue_jobs", "deadline_at")
    op.drop_column("automation_queue_jobs", "lease_owner")
