"""encrypt persisted Paymob payment tokens

Revision ID: f9c8e2a1b704
Revises: f2a7c9d1b430
"""

import os

from alembic import op
import sqlalchemy as sa
from cryptography.fernet import Fernet

revision = "f9c8e2a1b704"
down_revision = "f2a7c9d1b430"
branch_labels = None
depends_on = None

_COLUMN = "client_secret_encrypted"
_ENV = "KEMET_PAYMENT_ENCRYPTION_KEY"
_PREFIX = "v1:"


def _fernet():
    raw = os.getenv(_ENV, "").strip()
    if not raw:
        raise RuntimeError(f"{_ENV} is required to migrate payment tokens")
    return Fernet(raw.encode("utf-8"))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("payments"):
        return
    columns = {item["name"] for item in inspector.get_columns("payments")}
    if _COLUMN not in columns:
        op.add_column("payments", sa.Column(_COLUMN, sa.Text(), nullable=True))
    rows = list(bind.execute(sa.text(
        "SELECT id, client_secret FROM payments "
        "WHERE client_secret IS NOT NULL AND client_secret <> ''"
    )).mappings())
    if not rows:
        return
    fernet = _fernet()
    for row in rows:
        value = str(row["client_secret"] or "").strip()
        if value.startswith(_PREFIX):
            encrypted = value
        else:
            encrypted = _PREFIX + fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        bind.execute(
            sa.text("UPDATE payments SET client_secret_encrypted = :encrypted, client_secret = NULL WHERE id = :id"),
            {"encrypted": encrypted, "id": row["id"]},
        )
    bind.commit()


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("payments"):
        return
    columns = {item["name"] for item in inspector.get_columns("payments")}
    if _COLUMN not in columns:
        return
    rows = list(bind.execute(sa.text(
        "SELECT id, client_secret_encrypted FROM payments "
        "WHERE client_secret_encrypted IS NOT NULL"
    )).mappings())
    if rows:
        fernet = _fernet()
        for row in rows:
            stored = str(row["client_secret_encrypted"] or "")
            encrypted = stored[len(_PREFIX):] if stored.startswith(_PREFIX) else stored
            value = fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
            bind.execute(
                sa.text("UPDATE payments SET client_secret = :value WHERE id = :id"),
                {"value": value, "id": row["id"]},
            )
        bind.commit()
    op.drop_column("payments", _COLUMN)
