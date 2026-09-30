from app.services.mendes.mendes_script_voice_contract_service import mendes_script_voice_contract_service


def package(approved=True):
    return {"organization_id": 7, "package_digest": "p" * 64,
            "approval_status": "approved" if approved else "not_requested"}


def script():
    return {"script_digest": "s" * 64, "text": "Approved Arabic script."}


def voice(mode="tts"):
    return {"voice_id": "mendes-01", "mode": mode, "language": "ar_JO", "output_format": "wav"}


def test_requires_approved_script():
    result = mendes_script_voice_contract_service.build(
        organization_id=7, episode_package=package(False), approved_script=script(), voice_profile=voice()
    )
    assert result["status"] == "blocked"
    assert result["error"] == "script_approval_required"


def test_blocks_cross_tenant_package():
    p = package(True)
    p["organization_id"] = 8
    result = mendes_script_voice_contract_service.build(
        organization_id=7, episode_package=p, approved_script=script(), voice_profile=voice()
    )
    assert result["error"] == "episode_package_tenant_mismatch"


def test_clone_requires_rights_attestation():
    result = mendes_script_voice_contract_service.build(
        organization_id=7, episode_package=package(True), approved_script=script(), voice_profile=voice("clone")
    )
    assert result["status"] == "blocked"
    assert result["error"] == "voice_rights_attestation_required"


def test_approved_script_can_produce_governed_piper_voice_plan(monkeypatch):
    monkeypatch.setenv("KEMET_PIPER_EXECUTABLE", "/bin/sh")
    result = mendes_script_voice_contract_service.build(
        organization_id=7, episode_package=package(True), approved_script=script(), voice_profile=voice()
    )
    assert result["success"] is True
    assert result["contract"]["voice_plan"]["provider_id"] == "piper_local"
    assert result["contract"]["voice_plan"]["language"] == "ar_JO"
    assert result["contract"]["governance"]["execution_authority"] is False
    assert len(result["contract"]["contract_digest"]) == 64
