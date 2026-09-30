from app.services.wan_backend_adapter import wan_backend_adapter


def test_wan_preflight_waits_without_worker(monkeypatch):
    monkeypatch.delenv("KEMET_WAN_WORKER_URL", raising=False)
    out = wan_backend_adapter.preflight()
    assert out["status"] == "WAITING_FOR_REMOTE_WORKER"
    assert out["worker_snapshot"] is None


def test_wan_preflight_registers_unverified_worker(monkeypatch):
    monkeypatch.setenv("KEMET_WAN_WORKER_URL", "https://worker.example")
    out = wan_backend_adapter.preflight()
    assert out["status"] == "WAITING_FOR_WORKER_VERIFICATION"
    assert out["worker_snapshot"]["provider_id"] == "wan2_2_remote"
    assert out["worker_snapshot"]["healthy"] is False
    assert out["worker_snapshot"]["available"] is False


def test_wan_job_supports_cinematic_and_character_profiles():
    shot = {"shot_id": "golden-001", "canonical_shot_digest": "shot-digest"}
    assets = {"status": "BOUND", "references": ["mendes-front", "lab-hero"]}
    cinematic = wan_backend_adapter.build_job(organization_id=7, shot=shot, asset_gate=assets, profile_id="cinematic_i2v")
    animate = wan_backend_adapter.build_job(organization_id=7, shot=shot, asset_gate=assets, profile_id="character_animation")
    assert cinematic["render_profile"]["model"] == "Wan2.2-I2V-A14B"
    assert animate["render_profile"]["model"] == "Wan2.2-Animate-14B"
    assert cinematic["execution"]["remote_worker_required"] is True
