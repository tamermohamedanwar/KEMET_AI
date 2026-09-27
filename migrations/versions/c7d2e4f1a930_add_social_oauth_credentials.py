"""add durable social oauth state and encrypted credentials"""
from alembic import op
import sqlalchemy as sa

revision = "c7d2e4f1a930"
down_revision = "9b7e3c1d4a20"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "social_oauth_states" not in tables:
        op.create_table(
            "social_oauth_states",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("state_digest", sa.String(64), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(64), nullable=False),
            sa.Column("purpose", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("consumed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.UniqueConstraint("state_digest", name="uq_social_oauth_state_digest"),
        )
    if "encrypted_social_credentials" not in tables:
        op.create_table(
            "encrypted_social_credentials",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(64), nullable=False),
            sa.Column("credential_ref", sa.String(128), nullable=False),
            sa.Column("ciphertext", sa.Text(), nullable=False),
            sa.Column("key_version", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.UniqueConstraint("credential_ref", name="uq_social_credential_ref"),
            sa.UniqueConstraint("organization_id", "user_id", "channel", name="uq_social_credential_scope"),
        )


def downgrade():
    op.drop_table("encrypted_social_credentials")
    op.drop_table("social_oauth_states")
