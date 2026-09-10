"""add automation execution idempotency key

Revision ID: af02222e3cf3
Revises: c0489dc4f8ca
Create Date: 2026-08-23 11:27:48.633810

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'af02222e3cf3'
down_revision = 'c0489dc4f8ca'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "automation_executions",
        schema=None,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "idempotency_key",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_automation_executions_idempotency_key"),
            ["idempotency_key"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table(
        "automation_executions",
        schema=None,
    ) as batch_op:
        batch_op.drop_index(
            batch_op.f("ix_automation_executions_idempotency_key")
        )
        batch_op.drop_column("idempotency_key")

