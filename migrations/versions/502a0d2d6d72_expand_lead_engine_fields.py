"""expand lead engine fields

Revision ID: 502a0d2d6d72
Revises: 305e30b25782
"""

from alembic import op
import sqlalchemy as sa


revision = "502a0d2d6d72"
down_revision = "305e30b25782"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("demo_leads", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("phone", sa.String(length=50), nullable=True)
        )

        batch_op.add_column(
            sa.Column(
                "source",
                sa.String(length=50),
                nullable=False,
                server_default="website",
            )
        )

        batch_op.add_column(
            sa.Column(
                "lead_score",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

        batch_op.add_column(
            sa.Column(
                "estimated_value",
                sa.Numeric(precision=12, scale=2),
                nullable=False,
                server_default="0",
            )
        )

        batch_op.add_column(
            sa.Column("owner_id", sa.Integer(), nullable=True)
        )

        batch_op.add_column(
            sa.Column("notes", sa.Text(), nullable=True)
        )

        batch_op.add_column(
            sa.Column("last_contact_at", sa.DateTime(), nullable=True)
        )

        batch_op.add_column(
            sa.Column("next_follow_up_at", sa.DateTime(), nullable=True)
        )

        batch_op.add_column(
            sa.Column("converted_at", sa.DateTime(), nullable=True)
        )

        batch_op.add_column(
            sa.Column(
                "lost_reason",
                sa.String(length=255),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )

        batch_op.create_index(
            "ix_demo_leads_email",
            ["email"],
            unique=False,
        )

        batch_op.create_index(
            "ix_demo_leads_next_follow_up_at",
            ["next_follow_up_at"],
            unique=False,
        )

        batch_op.create_index(
            "ix_demo_leads_owner_id",
            ["owner_id"],
            unique=False,
        )

        batch_op.create_index(
            "ix_demo_leads_source",
            ["source"],
            unique=False,
        )

        batch_op.create_index(
            "ix_demo_leads_status",
            ["status"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_demo_leads_owner_id_users",
            "users",
            ["owner_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("demo_leads", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_demo_leads_owner_id_users",
            type_="foreignkey",
        )

        batch_op.drop_index("ix_demo_leads_status")
        batch_op.drop_index("ix_demo_leads_source")
        batch_op.drop_index("ix_demo_leads_owner_id")
        batch_op.drop_index("ix_demo_leads_next_follow_up_at")
        batch_op.drop_index("ix_demo_leads_email")

        batch_op.drop_column("updated_at")
        batch_op.drop_column("lost_reason")
        batch_op.drop_column("converted_at")
        batch_op.drop_column("next_follow_up_at")
        batch_op.drop_column("last_contact_at")
        batch_op.drop_column("notes")
        batch_op.drop_column("owner_id")
        batch_op.drop_column("estimated_value")
        batch_op.drop_column("lead_score")
        batch_op.drop_column("source")
        batch_op.drop_column("phone")
