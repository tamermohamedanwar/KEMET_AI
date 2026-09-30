"""reconcile verified model/live-schema drift

Revision ID: e1f4b7c9d620
Revises: d7f1e9a4c620

This migration repairs only schema differences proven safe against the
current SQLite database. Migration-owned historical KPI indexes are kept
represented in model metadata rather than recreated here.
"""

from alembic import op
import sqlalchemy as sa

revision = "e1f4b7c9d620"
down_revision = "d7f1e9a4c620"
branch_labels = None
depends_on = None


def _indexes(table):
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def _foreign_keys(table):
    return {
        (tuple(item["constrained_columns"]), item["referred_table"], tuple(item["referred_columns"]))
        for item in sa.inspect(op.get_bind()).get_foreign_keys(table)
    }


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("automation_queue_jobs"):
        columns = {c["name"]: c for c in inspector.get_columns("automation_queue_jobs")}
        if columns.get("state_updated_at", {}).get("nullable") is True:
            with op.batch_alter_table("automation_queue_jobs") as batch_op:
                batch_op.alter_column("state_updated_at", existing_type=sa.DateTime(), nullable=False)

    if inspector.has_table("conversations"):
        fks = _foreign_keys("conversations")
        if (("organization_id",), "organizations", ("id",)) not in fks:
            with op.batch_alter_table("conversations") as batch_op:
                batch_op.create_foreign_key("fk_conversations_organization_id", "organizations", ["organization_id"], ["id"])

    if inspector.has_table("demo_leads"):
        columns = {c["name"]: c for c in inspector.get_columns("demo_leads")}
        fks = _foreign_keys("demo_leads")
        if columns.get("created_at", {}).get("nullable") is True:
            with op.batch_alter_table("demo_leads") as batch_op:
                batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))
        if (("tenant_id",), "organizations", ("id",)) not in fks:
            with op.batch_alter_table("demo_leads") as batch_op:
                batch_op.create_foreign_key("fk_demo_leads_tenant_id", "organizations", ["tenant_id"], ["id"])

    if inspector.has_table("documents"):
        fks = _foreign_keys("documents")
        indexes = _indexes("documents")
        with op.batch_alter_table("documents") as batch_op:
            if "ix_documents_organization_id" not in indexes:
                batch_op.create_index("ix_documents_organization_id", ["organization_id"], unique=False)
            if (("organization_id",), "organizations", ("id",)) not in fks:
                batch_op.create_foreign_key("fk_documents_organization_id", "organizations", ["organization_id"], ["id"])

    if inspector.has_table("tickets"):
        columns = {c["name"]: c for c in inspector.get_columns("tickets")}
        fks = _foreign_keys("tickets")
        indexes = _indexes("tickets")
        with op.batch_alter_table("tickets") as batch_op:
            if columns.get("status", {}).get("nullable") is True:
                batch_op.alter_column("status", existing_type=sa.String(length=50), nullable=False)
            if "ix_tickets_message_hash" not in indexes:
                batch_op.create_index("ix_tickets_message_hash", ["message_hash"], unique=False)
            if "ix_tickets_user_id" not in indexes:
                batch_op.create_index("ix_tickets_user_id", ["user_id"], unique=False)
            if (("user_id",), "users", ("id",)) not in fks:
                batch_op.create_foreign_key("fk_tickets_user_id", "users", ["user_id"], ["id"])

    if inspector.has_table("users"):
        indexes = _indexes("users")
        with op.batch_alter_table("users") as batch_op:
            if "ix_users_oauth_id" not in indexes:
                batch_op.create_index("ix_users_oauth_id", ["oauth_id"], unique=False)
            if "ix_users_oauth_provider" not in indexes:
                batch_op.create_index("ix_users_oauth_provider", ["oauth_provider"], unique=False)

    if inspector.has_table("workforce_memberships"):
        indexes = _indexes("workforce_memberships")
        with op.batch_alter_table("workforce_memberships") as batch_op:
            if "uq_workforce_membership_org_agent" not in indexes:
                batch_op.create_index("uq_workforce_membership_org_agent", ["organization_id", "workforce_id"], unique=True)
            if "ix_workforce_memberships_organization_id" not in indexes:
                batch_op.create_index("ix_workforce_memberships_organization_id", ["organization_id"], unique=False)
            if "ix_workforce_memberships_workforce_id" not in indexes:
                batch_op.create_index("ix_workforce_memberships_workforce_id", ["workforce_id"], unique=False)
            if "ix_workforce_memberships_status" not in indexes:
                batch_op.create_index("ix_workforce_memberships_status", ["status"], unique=False)


def downgrade():
    if sa.inspect(op.get_bind()).has_table("workforce_memberships"):
        indexes = _indexes("workforce_memberships")
        with op.batch_alter_table("workforce_memberships") as batch_op:
            for name in ("ix_workforce_memberships_status", "ix_workforce_memberships_workforce_id", "ix_workforce_memberships_organization_id", "uq_workforce_membership_org_agent"):
                if name in indexes:
                    batch_op.drop_index(name)

    if sa.inspect(op.get_bind()).has_table("users"):
        indexes = _indexes("users")
        with op.batch_alter_table("users") as batch_op:
            for name in ("ix_users_oauth_provider", "ix_users_oauth_id"):
                if name in indexes:
                    batch_op.drop_index(name)

    if sa.inspect(op.get_bind()).has_table("tickets"):
        fks = _foreign_keys("tickets")
        indexes = _indexes("tickets")
        with op.batch_alter_table("tickets") as batch_op:
            if (("user_id",), "users", ("id",)) in fks:
                batch_op.drop_constraint("fk_tickets_user_id", type_="foreignkey")
            for name in ("ix_tickets_user_id", "ix_tickets_message_hash"):
                if name in indexes:
                    batch_op.drop_index(name)
            batch_op.alter_column("status", existing_type=sa.String(length=50), nullable=True)

    if sa.inspect(op.get_bind()).has_table("documents"):
        fks = _foreign_keys("documents")
        indexes = _indexes("documents")
        with op.batch_alter_table("documents") as batch_op:
            if (("organization_id",), "organizations", ("id",)) in fks:
                batch_op.drop_constraint("fk_documents_organization_id", type_="foreignkey")
            if "ix_documents_organization_id" in indexes:
                batch_op.drop_index("ix_documents_organization_id")

    if sa.inspect(op.get_bind()).has_table("demo_leads"):
        fks = _foreign_keys("demo_leads")
        with op.batch_alter_table("demo_leads") as batch_op:
            if (("tenant_id",), "organizations", ("id",)) in fks:
                batch_op.drop_constraint("fk_demo_leads_tenant_id", type_="foreignkey")
            batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP"))

    if sa.inspect(op.get_bind()).has_table("conversations"):
        fks = _foreign_keys("conversations")
        if (("organization_id",), "organizations", ("id",)) in fks:
            with op.batch_alter_table("conversations") as batch_op:
                batch_op.drop_constraint("fk_conversations_organization_id", type_="foreignkey")

    if sa.inspect(op.get_bind()).has_table("automation_queue_jobs"):
        columns = {c["name"]: c for c in sa.inspect(op.get_bind()).get_columns("automation_queue_jobs")}
        if columns.get("state_updated_at", {}).get("nullable") is False:
            with op.batch_alter_table("automation_queue_jobs") as batch_op:
                batch_op.alter_column("state_updated_at", existing_type=sa.DateTime(), nullable=True)
