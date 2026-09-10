from pathlib import Path


def test_automation_execution_persists_idempotency_key():
    source = Path("app/automation/engine.py").read_text()
    assert "idempotency_key=idempotency_key" in source


def test_kemet_core_imports_runtime_typing_symbols():
    from app.core.orchestration.kemet_core import KemetCore

    result = KemetCore().status()
    assert result["ok"] is True
    assert result["mode"] == "advisory"
