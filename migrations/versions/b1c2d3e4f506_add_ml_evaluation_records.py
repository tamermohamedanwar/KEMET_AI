"""add durable governed ML evaluation records

Revision ID: b1c2d3e4f506
Revises: aa10d4f6b820
"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f506"
down_revision = "aa10d4f6b820"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("ml_evaluation_records"):
        return
    op.create_table(
        "ml_evaluation_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("evaluation_key", sa.String(255), nullable=False),
        sa.Column("task_id", sa.String(255), nullable=False),
        sa.Column("dataset_id", sa.String(255), nullable=False),
        sa.Column("dataset_sha256", sa.String(64), nullable=False),
        sa.Column("authorization_reference", sa.String(255), nullable=False),
        sa.Column("authorization_digest", sa.String(64), nullable=False),
        sa.Column("intake_digest", sa.String(64), nullable=True),
        sa.Column("evaluation_digest", sa.String(64), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=True),
        sa.Column("evidence_completion_digest", sa.String(64), nullable=True),
        sa.Column("status", sa.String(64), nullable=False, default="review_required"),
        sa.Column("approval_status", sa.String(32), nullable=False, default="pending"),
        sa.Column("execution_status", sa.String(32), nullable=False, default="not_executed"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "evaluation_key", name="uq_ml_eval_org_key"),
    )
    for name, cols in {
        "ix_ml_eval_organization_id": ["organization_id"],
        "ix_ml_eval_task_id": ["task_id"],
        "ix_ml_eval_dataset_id": ["dataset_id"],
        "ix_ml_eval_dataset_sha256": ["dataset_sha256"],
        "ix_ml_eval_authorization_reference": ["authorization_reference"],
        "ix_ml_eval_status": ["status"],
        "ix_ml_eval_created_at": ["created_at"],
        "ix_ml_eval_org_status": ["organization_id", "status"],
        "ix_ml_eval_org_dataset": ["organization_id", "dataset_sha256"],
    }.items():
        op.create_index(name, "ml_evaluation_records", cols)


def downgrade():
    op.drop_table("ml_evaluation_records")
