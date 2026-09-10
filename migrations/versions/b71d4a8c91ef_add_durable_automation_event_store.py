"""add durable automation event store

Revision ID: b71d4a8c91ef
Revises: af02222e3cf3
Create Date: 2026-09-10

"""
from alembic import op
import sqlalchemy as sa


revision = "b71d4a8c91ef"
down_revision = "af02222e3cf3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "automation_event_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=150), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint(
            "organization_id", "source", "idempotency_key",
            name="uq_automation_event_org_source_idem",
        ),
    )
    for name, columns in (
        ("ix_automation_event_records_organization_id", ["organization_id"]),
        ("ix_automation_event_records_event_id", ["event_id"]),
        ("ix_automation_event_records_event_type", ["event_type"]),
        ("ix_automation_event_records_idempotency_key", ["idempotency_key"]),
        ("ix_automation_event_records_correlation_id", ["correlation_id"]),
        ("ix_automation_event_records_trace_id", ["trace_id"]),
        ("ix_automation_event_records_status", ["status"]),
    ):
        op.create_index(name, "automation_event_records", columns, unique=False)


def downgrade():
    for name in (
        "ix_automation_event_records_status",
        "ix_automation_event_records_trace_id",
        "ix_automation_event_records_correlation_id",
        "ix_automation_event_records_idempotency_key",
        "ix_automation_event_records_event_type",
        "ix_automation_event_records_event_id",
        "ix_automation_event_records_organization_id",
    ):
        op.drop_index(name, table_name="automation_event_records")
    op.drop_table("automation_event_records")
