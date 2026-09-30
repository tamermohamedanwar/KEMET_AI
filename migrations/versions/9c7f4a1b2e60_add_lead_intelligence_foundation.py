"""add lead intelligence foundation

Revision ID: 9c7f4a1b2e60
Revises: af02222e3cf3, f8b6d3e1a240
"""

from alembic import op
import sqlalchemy as sa

revision = "9c7f4a1b2e60"
down_revision = ("af02222e3cf3", "f8b6d3e1a240")
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("demo_leads")}
    columns = (
        ("tenant_id", "INTEGER"),
        ("provenance", "JSON"),
        ("freshness_at", "DATETIME"),
        ("confidence", "FLOAT NOT NULL DEFAULT 0"),
        ("evidence_digest", "VARCHAR(64)"),
        ("dedup_key", "VARCHAR(64)"),
        ("qualification_status", "VARCHAR(30)"),
        ("qualification_reason", "TEXT"),
    )
    for name, definition in columns:
        if name not in existing:
            op.execute(sa.text(f"ALTER TABLE demo_leads ADD COLUMN {name} {definition}"))

    op.execute(sa.text("UPDATE demo_leads SET tenant_id = organization_id WHERE tenant_id IS NULL AND organization_id IS NOT NULL"))
    for name, column in (
        ("ix_demo_leads_tenant_id", "tenant_id"),
        ("ix_demo_leads_freshness_at", "freshness_at"),
        ("ix_demo_leads_evidence_digest", "evidence_digest"),
        ("ix_demo_leads_dedup_key", "dedup_key"),
        ("ix_demo_leads_qualification_status", "qualification_status"),
    ):
        op.execute(sa.text(f"CREATE INDEX IF NOT EXISTS {name} ON demo_leads ({column})"))

    if not inspector.has_table("lead_intelligence_evidence"):
        op.create_table(
            "lead_intelligence_evidence",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("operation", sa.String(length=60), nullable=False),
            sa.Column("before_digest", sa.String(length=64), nullable=True),
            sa.Column("after_digest", sa.String(length=64), nullable=False),
            sa.Column("evidence_digest", sa.String(length=64), nullable=False),
            sa.Column("evidence_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["lead_id"], ["demo_leads.id"]),
            sa.UniqueConstraint("tenant_id", "lead_id", "operation", "after_digest", name="uq_lead_intelligence_evidence_step"),
        )


def downgrade():
    op.drop_table("lead_intelligence_evidence")
    for name in (
        "ix_demo_leads_qualification_status",
        "ix_demo_leads_dedup_key",
        "ix_demo_leads_evidence_digest",
        "ix_demo_leads_freshness_at",
        "ix_demo_leads_tenant_id",
    ):
        op.execute(sa.text(f"DROP INDEX IF EXISTS {name}"))
    for name in (
        "qualification_reason",
        "qualification_status",
        "dedup_key",
        "evidence_digest",
        "confidence",
        "freshness_at",
        "provenance",
        "tenant_id",
    ):
        op.execute(sa.text(f"ALTER TABLE demo_leads DROP COLUMN {name}"))
