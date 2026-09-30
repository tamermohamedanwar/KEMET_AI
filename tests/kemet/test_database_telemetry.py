from sqlalchemy import create_engine, text

from app.core.database_telemetry import DatabaseTelemetry


def test_database_telemetry_installs_on_sqlite_and_reports_pool():
    engine = create_engine("sqlite:///:memory:")
    telemetry = DatabaseTelemetry()
    telemetry.install(engine)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    snapshot = telemetry.snapshot()
    assert snapshot["schema"] == "kemet.database_telemetry.v1"
    assert snapshot["read_only"] is True
    assert snapshot["secret_exposed"] is False
    assert snapshot["pool"]["available"] is True
    assert snapshot["postgresql"]["available"] is False


def test_database_telemetry_install_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    telemetry = DatabaseTelemetry()
    telemetry.install(engine)
    telemetry.install(engine)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    assert telemetry.installed is True


def test_database_telemetry_never_returns_connection_values():
    engine = create_engine("sqlite:///:memory:")
    telemetry = DatabaseTelemetry()
    telemetry.install(engine)
    snapshot = telemetry.snapshot()
    serialized = str(snapshot).lower()
    assert snapshot["secret_exposed"] is False
    assert "sqlite://" not in serialized
    assert "postgresql://" not in serialized
    assert "password=" not in serialized
