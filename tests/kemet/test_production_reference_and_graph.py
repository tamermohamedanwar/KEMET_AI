from app.services.production_reference_service import production_reference_service
from app.services.cinematic_production_os import cinematic_production_os


def _ref(item_id, digest, role):
    return {"id": item_id, "version": 1, "digest": digest, "role": role}


def test_golden_reference_pack_is_provider_independent_and_canonical():
    pack = production_reference_service.build_pack(
        organization_id=1,
        project_id="pilot",
        visual_direction={"id": "cinematic"},
        characters=[_ref("mendes", "char-digest", "character")],
        worlds=[_ref("world-1", "world-digest", "world")],
    )
    assert pack["provider_independent"] is True
    assert pack["source_of_truth"] == "canonical_production_state"
    assert pack["invariants"]["character_identity"] is True
    assert pack["digest"]


def test_production_graph_requires_canonical_state_and_binds_reference():
    state = cinematic_production_os.build_state(
        organization_id=1, project_id="pilot", stage="visual_direction",
        intent={"task_type": "video"}, visual_direction={"id": "cinematic"},
    )
    pack = production_reference_service.build_pack(
        organization_id=1, project_id="pilot", visual_direction={"id": "cinematic"},
        characters=[_ref("mendes", "char-digest", "character")],
        worlds=[_ref("world-1", "world-digest", "world")],
    )
    graph = cinematic_production_os.build_graph(state=state, golden_reference=pack, shots=[{"shot_id": "sh1"}])
    assert graph["canonical"] is True
    assert graph["prompts_are_derived"] is True
    assert graph["golden_reference_digest"] == pack["digest"]
    assert graph["governance"]["mcp"] is False
    assert ["golden_reference", "character_identity"] in graph["edges"]
    assert ["golden_reference", "world_continuity"] in graph["edges"]
    assert ["storyboard", "previs"] in graph["edges"]


def test_golden_reference_requires_exact_bindings():
    try:
        production_reference_service.build_pack(
            organization_id=1, project_id="pilot", visual_direction={"id": "cinematic"},
            characters=[{"id": "mendes"}], worlds=[]
        )
    except ValueError as exc:
        assert str(exc) == "character_reference_exact_binding_required"
    else:
        raise AssertionError("inexact reference accepted")


def test_long_form_manifest_preserves_hierarchy_and_continuity():
    from app.services.long_form_production_service import long_form_production_service
    manifest = long_form_production_service.build_production_manifest(
        organization_id=1,
        project_id="series-1",
        project={"project_id": "series-1", "version": 1, "digest": "p"},
        seasons=[{"id": "s1", "version": 1, "digest": "s"}],
        episodes=[{"id": "e1", "version": 1, "digest": "e"}],
        sequences=[{"id": "q1", "version": 1, "digest": "q"}],
        scenes=[{"id": "sc1", "version": 1, "digest": "sc"}],
        shots=[{"id": "sh1", "version": 1, "canonical_shot_digest": "sh"}],
        characters=[{"id": "mendes", "version": 1, "digest": "c"}],
        worlds=[{"id": "world-1", "version": 1, "digest": "w"}],
        bibles={"character": "character-bible-v1", "world": "world-bible-v1", "continuity": "continuity-bible-v1"},
    )
    assert manifest["schema"] == "kemet.cinematic.production_manifest.v1"
    assert manifest["production_strategy"]["resumable"] is True
    assert manifest["production_strategy"]["targeted_regeneration"] is True
    assert manifest["continuity"]["cross_episode_state"] is True
    assert manifest["continuity"]["character_identity_persistent"] is True
    assert manifest["provider_independent"] is True
    assert manifest["governance"]["execution_authority"] is False
    assert manifest["digest"]


def test_long_form_manifest_fails_closed_on_missing_hierarchical_digest():
    from app.services.long_form_production_service import long_form_production_service
    try:
        long_form_production_service.build_production_manifest(
            organization_id=1, project_id="series-1",
            project={"project_id": "series-1", "version": 1, "digest": "p"},
            episodes=[{"id": "e1", "version": 1}],
        )
    except ValueError as exc:
        assert str(exc) == "episode_digest_required"
    else:
        raise AssertionError("undigested episode accepted")
