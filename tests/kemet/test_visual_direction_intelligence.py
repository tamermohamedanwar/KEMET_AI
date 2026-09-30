from app.services.visual_direction_service import visual_direction_service
from app.services.cinematic_production_os import cinematic_production_os


def test_visual_direction_service_prioritizes_cinematic_for_film_requests():
    directions = visual_direction_service.suggest("أنشئ إعلانًا سينمائيًا لـ Kemet")
    assert directions[0]["id"] == "cinematic"
    assert {item["id"] for item in directions} >= {"cinematic", "motion_graphics", "photoreal"}


def test_visual_direction_service_supports_cartoon_and_animation():
    directions = visual_direction_service.suggest("أريد فيلم كرتوني برسوم متحركة")
    ids = [item["id"] for item in directions]
    assert ids.index("cartoon") < ids.index("stylized")
    assert "animation" in ids


def test_production_state_binds_human_visual_direction_as_canonical_state():
    state = cinematic_production_os.build_state(
        organization_id=7,
        project_id="kemet-ai",
        stage="intent_visual_direction",
        intent={"task_type": "multimodal"},
        visual_direction={"id": "cinematic", "selected_by": "human"},
    )
    assert state["source_of_truth"] == "canonical_production_state"
    assert state["visual_direction"]["id"] == "cinematic"
    assert state["governance"]["mcp"] is False
    assert state["governance"]["human_approval_required"] is True
    assert state["digest"]
