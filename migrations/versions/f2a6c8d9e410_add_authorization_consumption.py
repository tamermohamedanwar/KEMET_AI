"""add durable one-time execution authorization consumption

Revision ID: f2a6c8d9e410
Revises: e7f4a9c2d610
"""
from alembic import op
import sqlalchemy as sa

revision = "f2a6c8d9e410"
down_revision = "e7f4a9c2d610"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("execution_authorization_consumption"):
        return
    bind = op.get_bind()
    if sa.inspect(bind).has_table("execution_authorization_consumption"):
        return
    op.create_table(
        "execution_authorization_consumption",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("plan_hash", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=255), nullable=True),
        sa.Column("approver_id", sa.Integer(), nullable=True),
        sa.Column("execution_key", sa.String(length=512), nullable=True),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_execution_auth_consumption_token_hash"),
    )
    for column in ("token_hash", "organization_id", "plan_hash", "action", "approver_id", "execution_key", "expires_at", "consumed_at", "created_at"):
        op.create_index(f"ix_execution_auth_consumption_{column}", "execution_authorization_consumption", [column])


def downgrade():
    op.drop_table("execution_authorization_consumption")
