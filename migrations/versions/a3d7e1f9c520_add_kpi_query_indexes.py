"""add KPI query indexes

Revision ID: a3d7e1f9c520
Revises: 9c7f4a1b2e60
"""

from alembic import op
import sqlalchemy as sa

revision = "a3d7e1f9c520"
down_revision = "9c7f4a1b2e60"
branch_labels = None
depends_on = None


INDEXES = (
    ("ix_automation_executions_created_workflow_status", "automation_executions", "created_at, workflow_id, status"),
    ("ix_tickets_org_created_status", "tickets", "organization_id, created_at, status"),
    ("ix_ticket_replies_created_ticket_ai_staff", "ticket_replies", "created_at, ticket_id, is_ai, is_staff"),
    ("ix_demo_leads_org_created_status", "demo_leads", "organization_id, created_at, status"),
    ("ix_payments_org_created_status", "payments", "organization_id, created_at, status"),
    ("ix_subscriptions_org_status", "subscriptions", "organization_id, status"),
    ("ix_ai_usage_org_created", "ai_usage", "organization_id, created_at"),
)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for name, table, columns in INDEXES:
        if table in tables:
            op.execute(sa.text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"))


def downgrade():
    for name, _, _ in INDEXES:
        op.execute(sa.text(f"DROP INDEX IF EXISTS {name}"))
