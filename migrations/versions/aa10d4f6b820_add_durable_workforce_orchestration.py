"""add durable workforce orchestration

Revision ID: aa10d4f6b820
Revises: a3d7e1f9c520
"""
from alembic import op
import sqlalchemy as sa

revision = "aa10d4f6b820"
down_revision = "a3d7e1f9c520"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "workforce_memberships" not in tables:
        op.create_table("workforce_memberships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("workforce_id", sa.String(120), nullable=False),
            sa.Column("role", sa.String(120), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("capabilities_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("allowed_actions_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("approval_actions_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("metrics_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("permission_version", sa.String(80), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False))
        op.create_index("uq_workforce_membership_org_agent", "workforce_memberships", ["organization_id", "workforce_id"], unique=True)
        op.create_index("ix_workforce_memberships_organization_id", "workforce_memberships", ["organization_id"])
        op.create_index("ix_workforce_memberships_workforce_id", "workforce_memberships", ["workforce_id"])

    if "workforce_assignments" not in tables:
        op.create_table("workforce_assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("membership_id", sa.Integer(), sa.ForeignKey("workforce_memberships.id"), nullable=False),
            sa.Column("workforce_id", sa.String(120), nullable=False),
            sa.Column("objective", sa.Text(), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="assigned"),
            sa.Column("idempotency_key", sa.String(255), nullable=False),
            sa.Column("permission_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("delegation_parent_id", sa.Integer(), nullable=True),
            sa.Column("plan_json", sa.Text(), nullable=True),
            sa.Column("plan_hash", sa.String(128), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False))
        op.create_index("uq_workforce_assignment_idempotency", "workforce_assignments", ["organization_id", "idempotency_key"], unique=True)
        for c in ("organization_id", "membership_id", "workforce_id", "status", "idempotency_key", "delegation_parent_id", "plan_hash", "created_at"):
            op.create_index(f"ix_workforce_assignments_{c}", "workforce_assignments", [c])

    if "workforce_tasks" not in tables:
        op.create_table("workforce_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("workforce_assignments.id"), nullable=False),
            sa.Column("workforce_id", sa.String(120), nullable=False),
            sa.Column("action", sa.String(255), nullable=False),
            sa.Column("state", sa.String(40), nullable=False, server_default="assigned"),
            sa.Column("idempotency_key", sa.String(255), nullable=False),
            sa.Column("execution_key", sa.String(255), nullable=True),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("permission_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("input_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("evidence_digest", sa.String(128), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True))
        op.create_index("uq_workforce_task_idempotency", "workforce_tasks", ["organization_id", "idempotency_key"], unique=True)
        for c in ("organization_id", "assignment_id", "workforce_id", "state", "idempotency_key", "execution_key", "created_at"):
            op.create_index(f"ix_workforce_tasks_{c}", "workforce_tasks", [c])

    if "workforce_task_events" not in tables:
        op.create_table("workforce_task_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("workforce_tasks.id"), nullable=False),
            sa.Column("from_state", sa.String(40), nullable=True),
            sa.Column("to_state", sa.String(40), nullable=False),
            sa.Column("actor", sa.String(255), nullable=False),
            sa.Column("reason", sa.String(500), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("metadata_digest", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False))
        for c in ("organization_id", "task_id", "to_state", "metadata_digest", "created_at"):
            op.create_index(f"ix_workforce_task_events_{c}", "workforce_task_events", [c])

    if "workforce_schedules" not in tables:
        op.create_table("workforce_schedules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("workforce_assignments.id"), nullable=False),
            sa.Column("schedule_key", sa.String(255), nullable=False),
            sa.Column("schedule_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("next_run_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False))
        op.create_index("uq_workforce_schedule_key", "workforce_schedules", ["organization_id", "schedule_key"], unique=True)
        for c in ("organization_id", "assignment_id", "schedule_key", "status", "next_run_at"):
            op.create_index(f"ix_workforce_schedules_{c}", "workforce_schedules", [c])


def downgrade():
    for table, indexes in (("workforce_schedules", ("uq_workforce_schedule_key",)), ("workforce_task_events", ()), ("workforce_tasks", ("uq_workforce_task_idempotency",)), ("workforce_assignments", ("uq_workforce_assignment_idempotency",)), ("workforce_memberships", ("uq_workforce_membership_org_agent",))):
        for index_name in indexes:
            op.drop_index(index_name, table_name=table)
        op.drop_table(table)
