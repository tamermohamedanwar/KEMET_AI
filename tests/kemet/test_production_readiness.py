from pathlib import Path
import shutil
from dotenv import load_dotenv
def test_readiness_route_exists():
    from app import create_app
    app = create_app()
    assert 'def readiness()' in Path('app/routes/api.py').read_text()
    assert '/ready' in Path('app/routes/api.py').read_text()

def test_readiness_contract_is_read_only():
    from app.services.production_readiness import production_readiness
    result = production_readiness.check()
    assert result["engine"] == "kemet_production_readiness"
    assert result["governance"]["read_only"] is True
    assert result["governance"]["database_mutation"] is False


def test_paymob_readiness_requires_webhook_secret(monkeypatch):
    from app.services.production_readiness import production_readiness
    monkeypatch.setenv("PAYMENT_MODE", "paymob")
    for key in (
        "PAYMOB_API_KEY",
        "PAYMOB_SECRET_KEY",
        "PAYMOB_PUBLIC_KEY",
        "PAYMOB_INTEGRATION_ID",
    ):
        monkeypatch.setenv(key, "configured")
    monkeypatch.delenv("PAYMOB_HMAC_SECRET", raising=False)
    result = production_readiness.check()
    assert result["checks"]["payment"] == "failed"


def test_mock_payment_mode_is_ready_for_payment_check(monkeypatch):
    from app.services.production_readiness import production_readiness
    monkeypatch.setenv("PAYMENT_MODE", "mock")
    result = production_readiness.check()
    assert result["checks"]["payment"] == "ok"


def test_observability_is_reported(monkeypatch):
    from app.services.production_readiness import production_readiness
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    result = production_readiness.check()
    assert result["checks"]["observability"] == "ok"


def test_missing_log_level_is_non_blocking_warning(monkeypatch):
    from app.services.production_readiness import production_readiness
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    result = production_readiness.check()
    assert result["checks"]["observability"] == "warning"


def test_invalid_log_level_is_reported_as_warning(monkeypatch):
    from app.services.production_readiness import production_readiness
    monkeypatch.setenv("LOG_LEVEL", "NOT_A_LOG_LEVEL")
    result = production_readiness.check()
    assert result["checks"]["observability"] == "warning"


def test_valid_log_levels_are_ready(monkeypatch):
    from app.services.production_readiness import production_readiness
    for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        monkeypatch.setenv("LOG_LEVEL", level)
        result = production_readiness.check()
        assert result["checks"]["observability"] == "ok"


def test_mock_payment_mode_blocks_production_readiness(monkeypatch):
    from app import create_app
    from app.services.production_readiness import production_readiness
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("PAYMENT_MODE", "mock")
    result = production_readiness.check()
    assert result["checks"]["payment"] == "failed"


def test_api_ready_returns_200_when_all_readiness_checks_pass(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("KEMET_EXECUTION_SECRET", "test-execution-secret")
    monkeypatch.setenv("PAYMENT_MODE", "mock")
    source = Path("instance/supportai.db")
    isolated_db = tmp_path / "readiness.db"
    shutil.copy2(source, isolated_db)
    from app import create_app
    import app as app_module
    monkeypatch.setattr(app_module, "DATABASE_URL", f"sqlite:///{isolated_db}")
    app = create_app()
    with app.test_client() as client:
        response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["checks"]["database_integrity_violations"] == 0


def test_api_ready_endpoint_is_registered():
    from app import create_app
    app = create_app()
    client = app.test_client()
    response = client.get("/api/ready")
    assert response.status_code in (200, 503)
    assert response.is_json


def test_production_requires_postgresql(monkeypatch):
    from app import create_app
    from app.services.production_readiness import production_readiness
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("PAYMENT_MODE", "paymob")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("KEMET_EXECUTION_SECRET", "test-execution-secret")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    for key in (
        "PAYMOB_API_KEY",
        "PAYMOB_SECRET_KEY",
        "PAYMOB_PUBLIC_KEY",
        "PAYMOB_INTEGRATION_ID",
        "PAYMOB_HMAC_SECRET",
    ):
        monkeypatch.setenv(key, "configured")
    app = create_app()
    with app.app_context():
        result = production_readiness.check()
    assert result["checks"]["database_dialect"] == "sqlite"
    assert result["checks"]["production_database"] == "failed"
    assert result["success"] is False
