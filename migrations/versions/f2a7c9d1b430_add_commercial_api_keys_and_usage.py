from alembic import op
import sqlalchemy as sa
revision = "f2a7c9d1b430"
down_revision = "e1f4b7c9d620"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key_prefix", sa.String(24), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("scopes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("requests_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("key_prefix"), sa.UniqueConstraint("key_hash"))
    op.create_index("ix_api_keys_organization_id","api_keys",["organization_id"])
    op.create_index("ix_api_keys_key_prefix","api_keys",["key_prefix"])
    op.create_index("ix_api_keys_key_hash","api_keys",["key_hash"])
    op.create_index("ix_api_keys_status","api_keys",["status"])
    op.create_table("api_usage_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_key_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("route", sa.String(255), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["api_key_id"],["api_keys.id"]),
        sa.ForeignKeyConstraint(["organization_id"],["organizations.id"]))
    for name, table, cols in [
        ("ix_api_usage_events_api_key_id","api_usage_events",["api_key_id"]),
        ("ix_api_usage_events_organization_id","api_usage_events",["organization_id"]),
        ("ix_api_usage_events_request_id","api_usage_events",["request_id"]),
        ("ix_api_usage_events_created_at","api_usage_events",["created_at"])]:
        op.create_index(name,table,cols)

def downgrade():
    op.drop_table("api_usage_events")
    op.drop_table("api_keys")
