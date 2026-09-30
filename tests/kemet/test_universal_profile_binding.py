from app.services.cinematic_production_os import cinematic_production_os
from app.services.cinematic_quality_readiness_gate import cinematic_quality_readiness_gate
from app.services.visual_direction_service import visual_direction_service


def _state(direction="motion_graphics"):
    return cinematic_production_os.build_state(
        organization_id=7, project_id="profile-1", stage="intent_visual_direction",
        visual_direction={"id": direction}, intent={"task_type": "multimodal"},
    )


def test_profile_is_bound_into_canonical_planning_specification():
    state = _state("motion_graphics")
    projection = cinematic_production_os.compile_planning_projection(state=state)
    profile = projection["narrative"]["production_profile"]
    assert profile["profile_id"] == "motion_graphics"
    assert profile["schema"] == "kemet.visual.production_profile.v1"
    assert projection["specification"]["production_profile"]["digest"] == profile["digest"]
    assert projection["planning_only"] is True
    assert projection["governance"]["mcp"] is False


def test_profile_specific_qa_is_consumed_by_existing_gate():
    profile = visual_direction_service.compile_profile("motion_graphics")
    evidence = {key: {"verified": True} for key in cinematic_quality_readiness_gate.REQUIRED}
    evidence["typography"] = {"verified": False}
    result = cinematic_quality_readiness_gate.evaluate(
        organization_id=7, project_id="profile-1", evidence=evidence, production_profile=profile
    )
    assert result["status"] == "BLOCKED"
    assert any(item["gate"] == "typography" for item in result["profile_checks"])


def test_educational_and_commercial_profiles_are_canonical_options():
    for direction in ("educational", "commercial"):
        state = _state(direction)
        projection = cinematic_production_os.compile_planning_projection(state=state)
        assert projection["specification"]["production_profile"]["profile_id"] == direction
