"""add durable provider connection records

Revision ID: d6e9f2a1b430
Revises: c4f8a1d9e520
"""
from alembic import op
import sqlalchemy as sa

revision = "d6e9f2a1b430"
down_revision = "c4f8a1d9e520"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("provider_connection_records"):
        return
    op.create_table(
        "provider_connection_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("scopes_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("credential_ref", sa.String(128), nullable=True),
        sa.Column("provider_account_ref", sa.String(255), nullable=True),
        sa.Column("provider_project_ref", sa.String(255), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("organization_id", "user_id", "provider_id", "mode", name="uq_provider_connection_scope"),
    )
    op.create_index("ix_provider_conn_org", "provider_connection_records", ["organization_id"])
    op.create_index("ix_provider_conn_user", "provider_connection_records", ["user_id"])
    op.create_index("ix_provider_conn_provider", "provider_connection_records", ["provider_id"])
    op.create_index("ix_provider_conn_status", "provider_connection_records", ["status"])


def downgrade():
    op.drop_table("provider_connection_records")
