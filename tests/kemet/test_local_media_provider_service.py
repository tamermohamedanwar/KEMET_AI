from app.services.local_media_provider_service import local_media_provider_service


def test_local_media_provider_is_discovery_only_and_untrusted(monkeypatch):
    monkeypatch.delenv("KEMET_VODER_EXECUTABLE", raising=False)
    monkeypatch.delenv("KEMET_PIPER_EXECUTABLE", raising=False)
    snapshot = local_media_provider_service.snapshot(7)
    piper = next(item for item in snapshot["providers"] if item["provider_id"] == "piper_local")
    voder = next(item for item in snapshot["providers"] if item["provider_id"] == "voder")
    assert piper["execution_authority"] is False
    assert voder["configured"] is False
    assert snapshot["governance"]["untrusted_infrastructure"] is True


def test_voice_plan_fails_closed_without_rights_attestation():
    result = local_media_provider_service.plan(
        organization_id=7,
        capability="voice_clone",
        input_uri="asset:voice-reference",
        output_format="wav",
    )
    assert result["status"] == "blocked"
    assert result["error"] == "voice_rights_attestation_required"
    assert result["execution_authority"] is False


def test_piper_is_canonical_local_tts_provider_when_configured(monkeypatch):
    monkeypatch.setenv("KEMET_PIPER_EXECUTABLE", "/bin/sh")
    monkeypatch.delenv("KEMET_VODER_EXECUTABLE", raising=False)
    kwargs = {
        "organization_id": 7,
        "capability": "tts",
        "input_uri": "asset:episode-script",
        "output_format": "wav",
        "language": "ar_JO",
    }
    first = local_media_provider_service.plan(**kwargs)
    second = local_media_provider_service.plan(**kwargs)
    assert first["success"] is True
    assert first["plan"]["provider_id"] == "piper_local"
    assert first["plan"]["provider_configured"] is True
    assert first["plan"]["plan_digest"] == second["plan"]["plan_digest"]
    assert first["plan"]["execution"]["canonical_runtime_only"] is True
    assert first["plan"]["governance"]["execution_authority"] is False


def test_production_studio_exposes_piper_and_voder_without_connecting_them(monkeypatch):
    monkeypatch.delenv("KEMET_VODER_EXECUTABLE", raising=False)
    monkeypatch.delenv("KEMET_PIPER_EXECUTABLE", raising=False)
    from app.services.production_studio_service import production_studio_service
    plan = production_studio_service.plan(organization_id=7, title="Mendes Pilot")
    voice = next(stage for stage in plan["stages"] if stage["stage"] == "voice")
    provider_ids = {item["provider_id"] for item in voice["local_media_providers"]}
    assert {"piper_local", "voder"}.issubset(provider_ids)
    assert voice["voice_policy"]["voice_clone_requires_rights_attestation"] is True
    assert plan["governance"]["external_execution"] is False
