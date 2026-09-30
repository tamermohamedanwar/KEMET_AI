from app.services.cinematic_production_layer import cinematic_production_layer

def char():
    return {"character_id": "mendes", "version": 2, "digest": "char-v2"}

def world():
    return {"world_id": "chemistry-lab", "version": 3, "digest": "world-v3"}

def plates():
    return [{"view": v, "asset_id": f"mendes-{v}", "digest": f"d-{v}"} for v in ("front", "profile", "three_quarter", "back", "full_body")]

def test_character_reference_plates_lock_identity():
    result = cinematic_production_layer.character_reference_plates(organization_id=1, character=char(), plates=plates())
    assert result["identity_invariants"]["face"] is True
    assert result["identity_invariants"]["body_proportions"] is True

def test_character_reference_plates_require_complete_views():
    try:
        cinematic_production_layer.character_reference_plates(organization_id=1, character=char(), plates=plates()[:-1])
    except ValueError as exc:
        assert str(exc).startswith("character_reference_plates_missing:")
    else:
        raise AssertionError("incomplete character plates accepted")

def test_world_reference_plates_lock_spatial_invariants():
    result = cinematic_production_layer.world_reference_plates(
        organization_id=1, world=world(),
        plates=[{"view": "hero", "asset_id": "lab-hero", "digest": "lab-digest"}],
    )
    assert result["invariants"]["geography"] is True
    assert result["invariants"]["spatial_relationships"] is True

def test_shot_plan_normalizes_director_controls():
    result = cinematic_production_layer.shot_plan(
        organization_id=1,
        scene={"scene_id": "s1", "visual_direction": {"id": "cinematic"}},
        shots=[{"shot_id": "s1-sh1", "action": "Mendes enters", "camera": {"angle": "eye_level"},
                "lens": "50mm", "movement": "slow_push", "framing": "medium_close_up",
                "duration_seconds": 6, "transition": "cut",
                "continuity_constraints": ["face_locked", "lab_geometry_locked"]}],
        character_bindings=[char()], world_binding=world(),
    )
    shot = result["shots"][0]
    assert shot["lens"] == "50mm"
    assert shot["movement"] == "slow_push"
    assert shot["duration_seconds"] == 6.0

def test_storyboard_and_previs_bind_reference_pack():
    pack = {"version": 1, "digest": "pack-v1"}
    storyboard = cinematic_production_layer.storyboard(
        organization_id=1, project_id="pilot", scenes=[{"scene_id": "s1"}],
        shots=[{"shot_id": "s1-sh1", "composition": {"subject": "Mendes"}}], reference_pack=pack)
    previs = cinematic_production_layer.previs(
        organization_id=1, project_id="pilot", storyboard=storyboard,
        camera_plan=[{"shot_id": "s1-sh1", "movement": "slow_push"}],
        blocking=[{"position": "doorway"}])
    assert storyboard["reference_pack_digest"] == "pack-v1"
    assert previs["storyboard_digest"] == storyboard["digest"]
