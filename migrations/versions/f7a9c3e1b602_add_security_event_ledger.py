"""add security event ledger

Revision ID: f7a9c3e1b602
Revises: e2f7a1c9d610
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a9c3e1b602"
down_revision = "e2f7a1c9d610"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("security_event_records"):
        return
    op.create_table(
        "security_event_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=160), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("event_hash", name="uq_security_event_hash"),
    )
    for column in ("correlation_id", "event_type", "actor_id", "organization_id", "action", "status", "severity", "event_hash", "created_at"):
        op.create_index(f"ix_security_event_{column}", "security_event_records", [column])


def downgrade():
    op.drop_table("security_event_records")
