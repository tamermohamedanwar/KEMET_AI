"""add federation context fabric tables

Revision ID: c4f8a1d9e520
Revises: b7c2d9e4f510
"""
from alembic import op
import sqlalchemy as sa

revision = "c4f8a1d9e520"
down_revision = "b7c2d9e4f510"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("federation_conversations") and inspector.has_table("federation_sessions"):
        return
    op.create_table(
        "federation_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(64), nullable=False),
        sa.Column("external_conversation_id", sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("task_id", sa.String(128), nullable=True),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("decisions_json", sa.JSON(), nullable=False),
        sa.Column("artifacts_json", sa.JSON(), nullable=False),
        sa.Column("source_metadata_json", sa.JSON(), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("organization_id", "provider_id", "external_conversation_id", name="uq_fed_conv_org_provider_external"),
    )
    op.create_index("ix_fed_conv_org", "federation_conversations", ["organization_id"])
    op.create_index("ix_fed_conv_user", "federation_conversations", ["user_id"])
    op.create_index("ix_fed_conv_provider", "federation_conversations", ["provider_id"])
    op.create_index("ix_fed_conv_task", "federation_conversations", ["task_id"])
    op.create_index("ix_fed_conv_hash", "federation_conversations", ["context_hash"])
    op.create_index("ix_fed_conv_active", "federation_conversations", ["active"])
    op.create_table(
        "federation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("task_id", sa.String(128), nullable=True),
        sa.Column("providers_json", sa.JSON(), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("organization_id", "session_id", name="uq_fed_session_org_id"),
    )
    op.create_index("ix_fed_session_org", "federation_sessions", ["organization_id"])
    op.create_index("ix_fed_session_user", "federation_sessions", ["user_id"])
    op.create_index("ix_fed_session_task", "federation_sessions", ["task_id"])
    op.create_index("ix_fed_session_active", "federation_sessions", ["active"])


def downgrade():
    op.drop_table("federation_sessions")
    op.drop_table("federation_conversations")
