"""add organization to conversations

Revision ID: 7f4e9b2c1d11
Revises: 1c1e9ae8281a
"""

from alembic import op
import sqlalchemy as sa


revision = "7f4e9b2c1d11"
down_revision = "1c1e9ae8281a"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        column["name"]
        for column in inspector.get_columns("conversations")
    }

    if "organization_id" not in columns:
        with op.batch_alter_table(
            "conversations",
            schema=None
        ) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "organization_id",
                    sa.Integer(),
                    nullable=True
                )
            )

            batch_op.create_index(
                "ix_conversations_organization_id",
                ["organization_id"],
                unique=False
            )

            batch_op.create_foreign_key(
                "fk_conversations_organization_id",
                "organizations",
                ["organization_id"],
                ["id"]
            )

    op.execute(
        sa.text("""
            UPDATE conversations
            SET organization_id = (
                SELECT users.organization_id
                FROM users
                WHERE users.id = conversations.user_id
            )
            WHERE organization_id IS NULL
        """)
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        column["name"]
        for column in inspector.get_columns("conversations")
    }

    if "organization_id" not in columns:
        return

    with op.batch_alter_table(
        "conversations",
        schema=None
    ) as batch_op:
        batch_op.drop_index(
            "ix_conversations_organization_id"
        )

        batch_op.drop_constraint(
            "fk_conversations_organization_id",
            type_="foreignkey"
        )

        batch_op.drop_column("organization_id")
