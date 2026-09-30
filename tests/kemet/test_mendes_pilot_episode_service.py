from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service


def test_pilot_build_is_tenant_bound_and_governed():
    result = mendes_pilot_episode_service.build(1)
    assert result["success"] is True
    package = result["package"]
    assert package["organization_id"] == 1
    assert package["world"] == "Mendes World"
    assert package["series"] == "Hikayat Mendes"
    assert package["episode"]["episode_id"] == "s1e1"
    assert package["approval"]["status"] == "pending"
    assert package["execution"]["automatic"] is False
    assert package["package_digest"]


def test_pilot_is_original_fiction_and_does_not_claim_history():
    package = mendes_pilot_episode_service.build(1)["package"]
    assert package["episode"]["era"]["type"] == "fictional"
    assert package["script"]["historical_claim"] is False
    assert package["script"]["rights_status"] == "original_content_planned"
    assert package["script"]["source_policy"]


def test_pilot_contains_production_scenes_and_outcome_measurement():
    package = mendes_pilot_episode_service.build(1)["package"]
    assert len(package["scenes"]) == 6
    assert package["production"]["governance"]["human_approval_required"] is True
    assert package["outcome"]["flow"] == [
        "story", "production", "quality_gate", "approval",
        "distribution", "measurement", "learning",
    ]
    assert package["outcome"]["governance"]["auto_publish"] is False


def test_pilot_voice_contract_has_no_selected_executor_or_clone_authority():
    package = mendes_pilot_episode_service.build(1)["package"]
    voice = package["voice_contract"]
    assert voice["provider"] == "piper_local"
    assert voice["voice_clone"] is False
    assert voice["execution_authority"] is False
    assert voice["rights_attestation_required"] is True


def test_pilot_rejects_invalid_tenant():
    try:
        mendes_pilot_episode_service.build(0)
    except ValueError as exc:
        assert str(exc) == "organization_required"
    else:
        raise AssertionError("invalid organization accepted")
