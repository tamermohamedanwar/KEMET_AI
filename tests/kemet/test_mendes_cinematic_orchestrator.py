from app.services.mendes.mendes_cinematic_orchestrator import mendes_cinematic_orchestrator


def _episode():
    return {
        "episode_id": "s1e1",
        "title": "الخاتم الأزرق",
        "characters": [
            {"character_id": "mendes-younes", "name": "يونس", "role": "protagonist", "traits": ["curious"], "family_id": "family-mendes", "status": "alive", "visual_identity": "original youthful Egyptian cartoon design", "voice_profile": "natural Egyptian Arabic"},
            {"character_id": "mendes-amna", "name": "آمنة", "role": "older_sister_and_guardian", "traits": ["protective"], "family_id": "family-mendes", "status": "alive", "visual_identity": "original Egyptian cartoon design, distinct silhouette", "voice_profile": "natural Egyptian Arabic"},
        ],
    }


def _scenes():
    return [{"description": "يونس يلتقط الخاتم", "characters": ["mendes-younes"], "dialogue": "إيه ده؟", "duration_seconds": 10}]


def _voice():
    return {"provider": "piper_local", "contract_digest": "v" * 64}


def test_cinematic_package_binds_canonical_character_and_world_identity():
    result = mendes_cinematic_orchestrator.build(organization_id=1, episode=_episode(), scenes=_scenes(), voice_contract=_voice())
    assert result["character_bindings"][0]["character_digest"]
    assert result["world_binding"]["world_digest"]
    assert result["shots"][0]["generation_prompt_status"] == "DERIVE_FROM_CANONICAL_BINDINGS"


def test_canonical_identity_is_stable_across_episode_builds():
    first = mendes_cinematic_orchestrator.build(organization_id=1, episode=_episode(), scenes=_scenes(), voice_contract=_voice())
    second = mendes_cinematic_orchestrator.build(organization_id=1, episode=_episode(), scenes=_scenes(), voice_contract=_voice())
    assert first["world_binding"]["world_digest"] == second["world_binding"]["world_digest"]
    assert first["character_bindings"][0]["character_digest"] == second["character_bindings"][0]["character_digest"]


def test_generation_prompt_is_derived_not_canonical_state():
    result = mendes_cinematic_orchestrator.build(organization_id=1, episode=_episode(), scenes=_scenes(), voice_contract=_voice())
    prompt = result["generation_prompts"][0]["prompt"]
    assert "Canonical characters:" in prompt
    assert "Preserve exact canonical identity" in prompt
    assert result["governance"]["prompts_are_derived_artifacts"] is True


def test_qa_uses_targeted_regeneration_policy():
    result = mendes_cinematic_orchestrator.build(organization_id=1, episode=_episode(), scenes=_scenes(), voice_contract=_voice())
    assert result["qa"]["status"] == "PASS"
    assert result["qa"]["regeneration_policy"]["whole_episode_regeneration"] is False
    assert result["qa"]["regeneration_policy"]["scope"] == "failed_asset_or_shot_only"


def test_governance_remains_human_approval_and_non_mcp():
    result = mendes_cinematic_orchestrator.build(organization_id=1, episode=_episode(), scenes=_scenes(), voice_contract=_voice())
    assert result["episode_graph"]["generation_policy"]["human_approval_required"] is True
    assert result["episode_graph"]["generation_policy"]["external_execution"] is False
    assert result["governance"]["mcp"] is False
