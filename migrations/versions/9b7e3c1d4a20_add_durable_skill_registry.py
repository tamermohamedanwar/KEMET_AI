"""add durable native skill registry"""
from alembic import op
import sqlalchemy as sa

revision = "9b7e3c1d4a20"
down_revision = "b72e4f1c9a30"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("skill_version_records"):
        return
    op.create_table(
        "skill_version_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("skill_id", sa.String(length=160), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved_by", sa.String(length=160), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.Column("admission_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("skill_id", "version", name="uq_skill_version_identity"),
    )
    for column in ("skill_id", "version", "digest", "status", "active", "created_at", "updated_at"):
        op.create_index(f"ix_skill_version_{column}", "skill_version_records", [column])


def downgrade():
    op.drop_table("skill_version_records")
