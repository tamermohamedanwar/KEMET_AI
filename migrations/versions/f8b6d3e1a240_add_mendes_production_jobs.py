"""add durable Mendes production jobs

Revision ID: f8b6d3e1a240
Revises: c7d2e4f1a930
"""
from alembic import op
import sqlalchemy as sa

revision = "f8b6d3e1a240"
down_revision = "c7d2e4f1a930"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("mendes_production_jobs"):
        op.create_table(
            "mendes_production_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.String(length=255), nullable=False),
            sa.Column("idempotency_key", sa.String(length=512), nullable=False),
            sa.Column("state", sa.String(length=40), nullable=False),
            sa.Column("episode_package_digest", sa.String(length=128), nullable=False),
            sa.Column("script_digest", sa.String(length=128), nullable=False),
            sa.Column("voice_contract_digest", sa.String(length=128), nullable=False),
            sa.Column("quality_gates_json", sa.Text(), nullable=False),
            sa.Column("approval_state", sa.String(length=40), nullable=False),
            sa.Column("asset_refs_json", sa.Text(), nullable=False),
            sa.Column("evidence_refs_json", sa.Text(), nullable=False),
            sa.Column("job_digest", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.UniqueConstraint("job_id"),
            sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_mendes_job_org_idempotency"),
        )
        for column in ("organization_id", "job_id", "idempotency_key", "state", "episode_package_digest", "script_digest", "voice_contract_digest", "job_digest", "created_at", "updated_at"):
            op.create_index(f"ix_mendes_job_{column}", "mendes_production_jobs", [column])
    if not inspector.has_table("mendes_production_job_transitions"):
        op.create_table(
            "mendes_production_job_transitions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.String(length=255), nullable=False),
            sa.Column("from_state", sa.String(length=40), nullable=False),
            sa.Column("to_state", sa.String(length=40), nullable=False),
            sa.Column("approval_granted", sa.Boolean(), nullable=False),
            sa.Column("transition_digest", sa.String(length=128), nullable=False),
            sa.Column("evidence_digest", sa.String(length=128), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        )
        for column in ("organization_id", "job_id", "transition_digest", "evidence_digest", "created_at"):
            op.create_index(f"ix_mendes_transition_{column}", "mendes_production_job_transitions", [column])


def downgrade():
    op.drop_table("mendes_production_job_transitions")
    op.drop_table("mendes_production_jobs")
