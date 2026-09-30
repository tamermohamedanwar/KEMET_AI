

def test_reference_pack_binds_universal_production_profile():
    from app.services.production_reference_service import production_reference_service
    from app.services.visual_direction_service import visual_direction_service
    profile = visual_direction_service.compile_profile("cinematic", task_type="commercial")
    pack = production_reference_service.build_pack(
        organization_id=1, project_id="profile-bound",
        visual_direction={"id": "cinematic"}, characters=[], worlds=[],
        production_profile=profile,
    )
    assert pack["production_profile"]["digest"] == profile["digest"]
    assert pack["production_profile"]["profile_id"] == "cinematic"
    assert pack["source_of_truth"] == "canonical_production_state"


def test_reference_pack_rejects_profile_direction_mismatch():
    from app.services.production_reference_service import production_reference_service
    from app.services.visual_direction_service import visual_direction_service
    profile = visual_direction_service.compile_profile("cartoon")
    try:
        production_reference_service.build_pack(
            organization_id=1, project_id="mismatch",
            visual_direction={"id": "cinematic"}, characters=[], worlds=[],
            production_profile=profile,
        )
    except ValueError as exc:
        assert str(exc) == "production_profile_direction_mismatch"
    else:
        raise AssertionError("expected production profile mismatch")
