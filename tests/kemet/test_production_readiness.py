from pathlib import Path
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
