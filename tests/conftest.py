import os
import shutil
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "instance" / "supportai.db"
TEST_DB = Path(tempfile.gettempdir()) / f"kemet_pytest_{os.getpid()}.db"
if SOURCE.exists():
    shutil.copy2(SOURCE, TEST_DB)
os.environ["FLASK_ENV"] = "testing"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["RATELIMIT_STORAGE_URI"] = "memory://"
os.environ["KEMET_EXECUTION_SECRET"] = "ci-test-execution-secret"
os.environ["KEMET_AGENT_TOKEN"] = "ci-test-agent-token"


def _sync_test_schema(app):
    """Bring the copied SQLite test snapshot up to the current ORM schema."""
    from sqlalchemy import inspect, text
    from app import db

    with app.app_context():
        inspector = inspect(db.engine)
        dialect = db.engine.dialect.name

        if dialect != "sqlite":
            return

        existing_tables = set(inspector.get_table_names())

        for table in db.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue

            existing_columns = {
                column["name"]
                for column in inspector.get_columns(table.name)
            }

            for column in table.columns:
                if column.name in existing_columns:
                    continue

                # SQLite supports ADD COLUMN for nullable/default-compatible
                # columns. Do not attempt destructive schema changes here.
                if not column.nullable and column.default is None and column.server_default is None:
                    raise RuntimeError(
                        f"Cannot safely add required test column "
                        f"{table.name}.{column.name}"
                    )

                column_type = column.type.compile(dialect=db.engine.dialect)
                statement = (
                    f'ALTER TABLE "{table.name}" '
                    f'ADD COLUMN "{column.name}" {column_type}'
                )

                db.session.execute(text(statement))

            db.session.commit()


@pytest.fixture(autouse=True)
def isolate_database_per_test():
    """Restore the canonical test snapshot before every test for deterministic isolation."""
    from wsgi import application
    from app import db

    with application.app_context():
        db.session.remove()
        db.engine.dispose()
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(f"{TEST_DB}{suffix}")
        if sidecar.exists():
            sidecar.unlink()
    if SOURCE.exists():
        shutil.copy2(SOURCE, TEST_DB)

    _sync_test_schema(application)

    yield
    with application.app_context():
        db.session.remove()
        db.engine.dispose()
