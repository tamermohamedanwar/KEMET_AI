from ops.release_hardening_gate import run


def test_release_contract_passes_without_production_secrets(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("KEMET_EXECUTION_SECRET", raising=False)
    report = run()
    assert report["status"] == "PASS_CONTRACT"
    assert report["production_claim"] is False
    assert report["secret_exposed"] is False


def test_release_contract_detects_required_runtime_secrets(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("KEMET_EXECUTION_SECRET", "test-execution-secret")
    report = run()
    assert report["status"] == "READY_FOR_PRODUCTION_EVIDENCE"
    assert report["production_claim"] is False


def test_release_contract_never_grants_production_claim(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("KEMET_EXECUTION_SECRET", "test-execution-secret")
    report = run()
    assert report["production_claim"] is False
    assert report["checks"]["production_database_gate"] is True
