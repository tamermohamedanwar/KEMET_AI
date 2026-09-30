from app.services.piper_tts_service import piper_tts_service


def test_piper_snapshot_is_free_local_and_non_executing(monkeypatch):
    monkeypatch.delenv("KEMET_PIPER_EXECUTABLE", raising=False)
    snapshot = piper_tts_service.snapshot(1)
    assert snapshot["provider_id"] == "piper_local"
    assert snapshot["cost_model"] == "local_no_api_fee"
    assert snapshot["credentials_required"] is False
    assert snapshot["execution_authority"] is False


def test_piper_plan_fails_closed_when_runtime_is_missing(monkeypatch):
    monkeypatch.delenv("KEMET_PIPER_EXECUTABLE", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    result = piper_tts_service.plan(
        organization_id=1,
        text="Kemet test",
        output_path="/tmp/kemet-test.wav",
    )
    assert result["success"] is False
    assert result["error"] == "piper_executable_not_configured"
    assert result["execution_authority"] is False


def test_piper_plan_is_governed_when_runtime_exists(monkeypatch, tmp_path):
    executable = tmp_path / "piper"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    monkeypatch.setenv("KEMET_PIPER_EXECUTABLE", str(executable))
    result = piper_tts_service.plan(
        organization_id=1,
        text="Kemet test",
        output_path="/tmp/kemet-test.wav",
    )
    assert result["success"] is True
    assert result["plan"]["provider_id"] == "piper_local"
    assert result["plan"]["credentials_required"] is False
    assert result["plan"]["execution"]["automatic"] is False
    assert result["plan"]["governance"]["execution_authority"] is False
    assert len(result["plan"]["plan_digest"]) == 64
