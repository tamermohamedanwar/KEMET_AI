import pytest

from app.core.media.contracts import (
    CAPABILITY_STATES,
    LICENSE_STATES,
    QA_STATES,
    VISUAL_PRODUCTION_STAGES,
    VISUAL_STYLE_FAMILIES,
    VISUAL_STYLE_CONTRACT,
    build_visual_production_job,
    build_visual_style,
    validate_capability_state,
    validate_license_state,
    validate_qa_state,
    validate_contract,
)


def style_payload():
    return {
        "visual_language": "premium cinematic",
        "camera_language": "controlled dolly",
        "lighting_language": "motivated cinematic",
        "color_language": "brand calibrated",
        "motion_language": "natural controlled",
        "texture_language": "physically plausible",
        "character_rules": {"identity_locked": True},
        "environment_rules": {"continuity_locked": True},
        "typography_rules": {"render_in_post": True},
        "aspect_ratio": "16:9",
        "shot_duration_range": {"min": 2, "max": 12},
        "reference_policy": {"required": True},
        "consistency_policy": {"character": "locked", "world": "locked"},
        "qa_policy": {"required": True},
    }


def test_visual_style_contract_covers_all_required_families():
    assert len(VISUAL_STYLE_FAMILIES) == 13
    style = build_visual_style(
        organization_id=1, style_id="premium-cinema", family="CINEMATIC_LIVE_ACTION",
        payload=style_payload(), contract_id="style-1",
    )
    assert style["schema"] == VISUAL_STYLE_CONTRACT
    assert validate_contract(style)["digest"] == style["digest"]


def test_visual_production_job_has_one_canonical_stage_graph():
    style = build_visual_style(
        organization_id=1, style_id="cartoon", family="TWO_D_CARTOON",
        payload=style_payload(), contract_id="style-2",
    )
    job = build_visual_production_job(organization_id=1, job_id="job-1", style=style)
    assert tuple(job["payload"]["stages"]) == VISUAL_PRODUCTION_STAGES
    assert job["payload"]["governance"]["execution_authority"] is False


def test_unknown_stage_is_rejected():
    style = build_visual_style(
        organization_id=1, style_id="toon", family="THREE_D_ANIMATION",
        payload=style_payload(), contract_id="style-3",
    )
    with pytest.raises(ValueError, match="unknown_visual_production_stage"):
        build_visual_production_job(organization_id=1, job_id="job-2", style=style, stages={"NOPE": {}})
