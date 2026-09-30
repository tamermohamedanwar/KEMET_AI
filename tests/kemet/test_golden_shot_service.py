from app.services.golden_shot_service import golden_shot_service


def _state():
    return {"organization_id": 1, "project_id": "golden", "digest": "a" * 64}


def _pack():
    return {"organization_id": 1, "digest": "b" * 64}


def _shot_plan():
    return {"shots": [{"shot_id": "golden-001", "action": "Mendes enters the chemistry lab", "camera": {"angle": "eye_level"}, "lens": "50mm", "framing": "medium", "movement": "slow_push", "lighting": {"key": "soft"}, "duration_seconds": 6, "character_bindings": [{"id": "mendes"}], "world_binding": {"id": "lab"}, "reference_asset_ids": ["mendes-front", "lab-hero"]}]}


def test_golden_shot_package_is_canonical_and_single_shot():
    package = golden_shot_service.build_package(
        organization_id=1, production_state=_state(), reference_pack=_pack(),
        character_plates=[{"digest": "c" * 64}], world_plates=[{"digest": "d" * 64}],
        shot_plan=_shot_plan(), storyboard={"digest": "e" * 64}, previs={"digest": "f" * 64},
    )
    assert package["canonical"] is True
    assert package["prompts_are_derived"] is True
    assert package["status"] == "READY_FOR_APPROVAL"
    assert package["shot"]["canonical_shot_digest"]
    assert package["shot"]["provider_prompt"]


def test_golden_shot_requires_human_approval():
    package = golden_shot_service.build_package(
        organization_id=1, production_state=_state(), reference_pack=_pack(),
        character_plates=[{"digest": "c" * 64}], world_plates=[{"digest": "d" * 64}],
        shot_plan=_shot_plan(), storyboard={"digest": "e" * 64}, previs={"digest": "f" * 64},
    )
    result = golden_shot_service.execute(package=package, approval={"approved": False}, output_dir="/tmp/kemet-golden")
    assert result["status"] == "blocked"
    assert result["error"] == "human_approval_required"
    assert result["executed"] is False


def test_golden_shot_preflight_reports_provider_and_render_capabilities():
    result = golden_shot_service.preflight(organization_id=1)
    assert result["schema"].endswith("golden_shot.v1")
    assert result["render"]["renderer"] == "ffmpeg-local"
    assert result["governance"]["mcp"] is False


def test_golden_shot_package_preserves_reference_profile_binding():
    from app.services.visual_direction_service import visual_direction_service
    profile = visual_direction_service.compile_profile("cinematic", task_type="commercial")
    pack = {"organization_id": 1, "digest": "b" * 64, "production_profile": profile}
    state = {"organization_id": 1, "project_id": "golden", "digest": "a" * 64, "visual_direction": {"id": "cinematic"}}
    package = golden_shot_service.build_package(
        organization_id=1, production_state=state, reference_pack=pack,
        character_plates=[{"digest": "c" * 64}], world_plates=[{"digest": "d" * 64}],
        shot_plan=_shot_plan(), storyboard={"digest": "e" * 64}, previs={"digest": "f" * 64},
    )
    assert package["production_profile"]["digest"] == profile["digest"]
    assert package["production_profile"]["profile_id"] == "cinematic"


def _procedural_inputs():
    return {
        "production_state": {"organization_id": 1, "project_id": "control-layer", "digest": "a" * 64},
        "reference_pack": {"organization_id": 1, "digest": "b" * 64},
        "character_plates": [],
        "world_plates": [],
        "shot_plan": {"shots": [
            {"shot_id": "control-001", "action": "Fragmented business systems converge into Kemet", "duration_seconds": 45}
        ]},
        "storyboard": {"digest": "e" * 64},
        "previs": {"digest": "f" * 64},
    }


def test_procedural_generation_mode_is_first_class_golden_artifact():
    inputs = _procedural_inputs()
    package = golden_shot_service.build_package(
        organization_id=1,
        generation_mode="KEMET_PROCEDURAL",
        artifact={"organization_id": 1, "digest": "1" * 64, "artifact_id": "artifact-1"},
        qa={"status": "PASS"},
        provenance={"digest": "2" * 64},
        procedural_plan={"duration_seconds": 45, "source_spec": {"type": "lavfi", "value": "color=c=black:s=1280x720:r=24:d=45"}},
        **inputs,
    )
    assert package["generation_mode"] == "KEMET_PROCEDURAL"
    assert package["artifact_kind"] == "COMMERCIAL"
    assert package["governance"]["canonical_executor"] == "kemet"
    assert package["governance"]["external_execution"] is False
    assert package["governance"]["mcp"] is False
    assert package["governance"]["network"] == "disabled"


def test_unknown_generation_mode_is_rejected():
    inputs = _procedural_inputs()
    try:
        golden_shot_service.build_package(organization_id=1, generation_mode="UNKNOWN", **inputs)
    except ValueError as exc:
        assert str(exc) == "generation_mode_invalid"
    else:
        raise AssertionError("unknown generation mode must be rejected")


def test_procedural_execution_requires_real_execution_authorization():
    inputs = _procedural_inputs()
    package = golden_shot_service.build_package(
        organization_id=1,
        generation_mode="KEMET_PROCEDURAL",
        procedural_plan={"duration_seconds": 45, "source_spec": {"type": "lavfi", "value": "color=c=black:s=1280x720:r=24:d=45"}},
        **inputs,
    )
    result = golden_shot_service.execute(
        package=package,
        approval={
            "approved": True,
            "organization_id": 1,
            "shot_id": package["shot"]["shot_id"],
            "canonical_shot_digest": package["shot"]["canonical_shot_digest"],
        },
        output_dir="/tmp/kemet-procedural-golden",
    )
    assert result["status"] == "blocked"
    assert result["error"] == "execution_authorization_required"
    assert result["executed"] is False


def test_procedural_artifact_requires_tenant_and_qa_integrity():
    inputs = _procedural_inputs()
    try:
        golden_shot_service.build_package(
            organization_id=1,
            generation_mode="KEMET_PROCEDURAL",
            artifact={"organization_id": 2, "digest": "1" * 64},
            qa={"status": "PASS"},
            **inputs,
        )
    except ValueError as exc:
        assert str(exc) == "artifact_tenant_mismatch"
    else:
        raise AssertionError("artifact tenant mismatch must be rejected")

    try:
        golden_shot_service.build_package(
            organization_id=1,
            generation_mode="KEMET_PROCEDURAL",
            artifact={"organization_id": 1, "digest": "1" * 64},
            qa={"status": "FAIL"},
            **inputs,
        )
    except ValueError as exc:
        assert str(exc) == "artifact_qa_required"
    else:
        raise AssertionError("failed QA must be rejected")
