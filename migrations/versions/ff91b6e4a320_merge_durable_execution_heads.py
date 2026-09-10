"""merge durable execution and orchestration migration heads

Revision ID: ff91b6e4a320
Revises: a8c5d7e2f310, d14e6f8b3a21
"""
from alembic import op

revision = "ff91b6e4a320"
down_revision = ("a8c5d7e2f310", "d14e6f8b3a21")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
