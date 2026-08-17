"""add ticket reply source message

Revision ID: 2147ec12a0eb
Revises: dc5632a5c418
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa


revision = "2147ec12a0eb"
down_revision = "dc5632a5c418"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ticket_replies",
        sa.Column(
            "source_message",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "ticket_replies",
        "source_message",
    )
