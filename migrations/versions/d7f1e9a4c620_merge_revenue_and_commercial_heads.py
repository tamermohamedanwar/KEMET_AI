"""Merge the reconciled revenue-pipeline and commercial-offer migration heads.

Revision ID: d7f1e9a4c620
Revises: 9d7e2c1a5b40, c9e4f2a7b610
"""

from alembic import op


revision = "d7f1e9a4c620"
down_revision = ("9d7e2c1a5b40", "c9e4f2a7b610")
branch_labels = None
depends_on = None


def upgrade():
    # The live baseline already contains both branch schemas.
    # This revision only records their verified convergence.
    pass


def downgrade():
    # No schema operation is introduced by the merge revision.
    pass
