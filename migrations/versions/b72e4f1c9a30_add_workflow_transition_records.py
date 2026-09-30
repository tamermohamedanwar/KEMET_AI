"""add durable unified workflow transition history

Revision ID: b72e4f1c9a30
Revises: a81c2d9e4b70
"""
from alembic import op
import sqlalchemy as sa

revision = "b72e4f1c9a30"
down_revision = "a81c2d9e4b70"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "workflow_transition_records" not in tables:
        op.create_table(
            "workflow_transition_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("job_id", sa.String(length=255), nullable=False),
            sa.Column("workflow_id", sa.String(length=255), nullable=False),
            sa.Column("execution_id", sa.String(length=255), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("from_state", sa.String(length=40), nullable=False),
            sa.Column("to_state", sa.String(length=40), nullable=False),
            sa.Column("reason", sa.String(length=500), nullable=True),
            sa.Column("actor", sa.String(length=255), nullable=True),
            sa.Column("plan_hash", sa.String(length=128), nullable=True),
            sa.Column("decision_hash", sa.String(length=128), nullable=True),
            sa.Column("approval_id", sa.String(length=255), nullable=True),
            sa.Column("execution_key", sa.String(length=255), nullable=True),
            sa.Column("metadata_digest", sa.String(length=64), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    indexes = {idx["name"] for idx in inspector.get_indexes("workflow_transition_records")}
    for name in ("job_id", "workflow_id", "execution_id", "idempotency_key", "plan_hash", "decision_hash", "approval_id", "execution_key", "created_at"):
        index_name = "ix_workflow_transition_records_" + name
        if index_name not in indexes:
            op.create_index(index_name, "workflow_transition_records", [name], unique=False)
    if "ix_workflow_transition_identity" not in indexes:
        op.create_index("ix_workflow_transition_identity", "workflow_transition_records", ["organization_id", "job_id", "created_at"], unique=False)


def downgrade():
    bind = op.get_bind()
    if "workflow_transition_records" not in sa.inspect(bind).get_table_names():
        return
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("workflow_transition_records")}
    for name in ("ix_workflow_transition_identity", "ix_workflow_transition_records_job_id", "ix_workflow_transition_records_workflow_id", "ix_workflow_transition_records_execution_id", "ix_workflow_transition_records_idempotency_key", "ix_workflow_transition_records_plan_hash", "ix_workflow_transition_records_decision_hash", "ix_workflow_transition_records_approval_id", "ix_workflow_transition_records_execution_key", "ix_workflow_transition_records_created_at"):
        if name in indexes:
            op.drop_index(name, table_name="workflow_transition_records")
    op.drop_table("workflow_transition_records")
