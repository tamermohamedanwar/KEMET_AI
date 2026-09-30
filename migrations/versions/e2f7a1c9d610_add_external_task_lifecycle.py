"""add durable external task lifecycle

Revision ID: e2f7a1c9d610
Revises: d6e9f2a1b430
"""
from alembic import op
import sqlalchemy as sa

revision = "e2f7a1c9d610"
down_revision = "d6e9f2a1b430"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("external_task_records"):
        return
    op.create_table(
        "external_task_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(length=80), nullable=False),
        sa.Column("external_task_id", sa.String(length=255), nullable=False),
        sa.Column("execution_key", sa.String(length=512), nullable=False),
        sa.Column("plan_hash", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("provider_id", "external_task_id", name="uq_external_task_provider_id"),
        sa.UniqueConstraint("organization_id", "execution_key", "action", name="uq_external_task_execution_action"),
    )
    for column in ("organization_id", "provider_id", "external_task_id", "execution_key", "plan_hash", "action", "status", "request_id", "created_at", "updated_at", "last_seen_at"):
        op.create_index(f"ix_external_task_{column}", "external_task_records", [column])


def downgrade():
    op.drop_table("external_task_records")
