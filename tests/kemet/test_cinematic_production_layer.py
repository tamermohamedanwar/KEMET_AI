from app.services.cinematic_production_layer import cinematic_production_layer


def _char(cid='c1'):
    return {'character_id': cid, 'version': 1, 'digest': f'digest-{cid}', 'identity': {'name': 'Mendes'},
            'visual_identity': {'face': 'canonical'}, 'visual_bible': {'forbidden_variations': ['different_face']},
            'voice_profile': {'voice_id': 'mendes-ar-eg'}}


def _world():
    return {'world_id': 'w1', 'version': 1, 'digest': 'world-digest', 'visual_style': {'style': 'cinematic'}}


def test_character_identity_is_exactly_bound():
    result = cinematic_production_layer.character_identity(organization_id=1, character=_char(), version=1)
    assert result['character_digest'] == 'digest-c1'
    assert result['status'] == 'CANONICAL_IDENTITY_BINDING'


def test_world_continuity_is_exactly_bound():
    result = cinematic_production_layer.world_continuity(organization_id=1, world=_world(), version=1)
    assert result['world_digest'] == 'world-digest'


def test_shot_plan_locks_character_and_world():
    result = cinematic_production_layer.shot_plan(organization_id=1, scene={'scene_id': 's1'}, shots=[{'action': 'walk'}], character_bindings=[_char()], world_binding=_world())
    assert result['shots'][0]['character_bindings'][0]['digest'] == 'digest-c1'
    assert result['shots'][0]['world_binding']['digest'] == 'world-digest'
    assert result['shots'][0]['generation_prompt_status'] == 'DERIVE_FROM_CANONICAL_BINDINGS'


def test_targeted_regeneration_policy():
    graph = {'digest': 'episode-digest'}
    result = cinematic_production_layer.qa(organization_id=1, episode_graph=graph, findings=[{'code': 'character_drift'}])
    assert result['status'] == 'FAIL'
    assert result['regeneration_policy']['scope'] == 'failed_asset_or_shot_only'
    assert result['regeneration_policy']['whole_episode_regeneration'] is False


def test_generation_prompt_is_derived_not_canonical():
    prompt = cinematic_production_layer.build_generation_prompt(shot={'shot_id': 'sh1', 'action': 'walk', 'camera': 'close'}, character_bindings=[{'id': 'c1'}], world_binding={'id': 'w1', 'version': 1})
    assert 'c1' in prompt and 'w1' in prompt


def test_planning_projection_binds_story_world_and_characters_without_execution():
    from app.services.cinematic_production_os import cinematic_production_os
    state = cinematic_production_os.build_state(organization_id=1, project_id="pilot", stage="intent_visual_direction",
        visual_direction={"id": "cinematic"}, intent={"task_type": "multimodal"})
    projection = cinematic_production_os.compile_planning_projection(
        state=state,
        story={"story_id": "story-1", "version": 1, "digest": "story-d1", "logline": "control"},
        characters=[{"character_id": "mendes", "version": 2, "digest": "char-v2"}],
        world={"world_id": "chemistry-lab", "version": 3, "digest": "world-v3"},
    )
    narrative = projection["narrative"]
    assert narrative["status"] == {"story": "bound", "world": "bound", "characters": "bound", "visual_direction": "selected", "shots": "pending"}
    assert narrative["characters"][0]["character_digest"] == "char-v2"
    assert narrative["world"]["world_digest"] == "world-v3"
    assert narrative["planning_only"] is True
    assert narrative["governance"]["external_execution"] is False
    assert projection["governance"]["execution_authority"] is False

def test_production_memory_persists_identity_style_voice_and_continuity():
    result = cinematic_production_layer.production_memory(
        organization_id=1,
        project_id="series-1",
        characters=[{"character_id":"mendes","version":2,"digest":"c2","state":{"wardrobe":"v3"}}],
        worlds=[{"world_id":"lab","version":4,"digest":"w4","state":{"weather":"night"}}],
        style={"visual_language":"cinematic","camera_language":"anamorphic"},
        voice_profiles=[{"id":"mendes-voice","version":1,"digest":"v1","state":{"dialect":"ar-EG"}}],
        continuity_state=[{"episode_id":"e4","timeline_position":120.0}],
    )
    assert result["schema"] == "kemet.cinematic.production_memory.v1"
    assert result["canonical"] is True
    assert result["policy"]["unapproved_outputs_are_noncanonical"] is True
    assert result["characters"][0]["id"] == "mendes"
    assert result["worlds"][0]["id"] == "lab"
    assert result["style"]["digest"]
    assert result["voices"][0]["id"] == "mendes-voice"


def test_continuity_impact_localizes_changed_character():
    result = cinematic_production_layer.continuity_impact(
        organization_id=1,
        changed_entity={"character_id":"mendes","version":3,"digest":"c3"},
        downstream=[
            {"shot_id":"sh21","episode_id":"e4","character_ids":["mendes"]},
            {"shot_id":"sh22","episode_id":"e4","character_ids":["other"]},
            {"shot_id":"sh23","episode_id":"e5","references":[{"id":"mendes"}]},
        ],
    )
    assert [x["shot_id"] for x in result["affected"]] == ["sh21","sh23"]
    assert [x["shot_id"] for x in result["unaffected"]] == ["sh22"]
    assert result["policy"]["regenerate_affected_only"] is True
    assert result["digest"]


def test_continuity_impact_fails_closed_without_exact_binding():
    try:
        cinematic_production_layer.continuity_impact(
            organization_id=1, changed_entity={"character_id":"mendes", "version":3},
            downstream=[],
        )
    except ValueError as exc:
        assert str(exc) == "changed_entity_exact_binding_required"
    else:
        raise AssertionError("unbound canonical change accepted")
