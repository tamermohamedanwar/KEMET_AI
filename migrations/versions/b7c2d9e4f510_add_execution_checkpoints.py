"""add durable per-step execution checkpoints

Revision ID: b7c2d9e4f510
Revises: ff91b6e4a320
"""
from alembic import op
import sqlalchemy as sa

revision = "b7c2d9e4f510"
down_revision = "ff91b6e4a320"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "automation_execution_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("execution_key", sa.String(length=512), nullable=False),
        sa.Column("plan_hash", sa.String(length=128), nullable=False),
        sa.Column("step_id", sa.String(length=255), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("organization_id", "execution_key", "step_id", name="uq_execution_checkpoint_org_key_step"),
    )
    for column in ("organization_id", "execution_key", "plan_hash", "step_id", "ordinal", "status", "worker_id", "created_at", "updated_at"):
        op.create_index(f"ix_execution_checkpoint_{column}", "automation_execution_checkpoints", [column])


def downgrade():
    op.drop_table("automation_execution_checkpoints")
