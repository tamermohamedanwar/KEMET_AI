from app.services.visual_direction_service import visual_direction_service


def test_universal_profiles_are_provider_independent_and_style_aware():
    for direction in ("cinematic", "cartoon", "animation", "motion_graphics", "photoreal", "stylized", "custom"):
        profile = visual_direction_service.compile_profile(direction, task_type="multimodal")
        assert profile["schema"] == "kemet.visual.production_profile.v1"
        assert profile["provider_independent"] is True
        assert profile["canonical_state_source"] == "canonical_production_state"
        assert profile["prompts_are_derived"] is True
        assert profile["planning_only"] is True
        assert profile["governance"]["human_approval_required"] is True
        assert profile["governance"]["mcp"] is False
        assert profile["first_class_assets"]
        assert profile["qa_dimensions"]
        assert profile["digest"]


def test_motion_graphics_treats_typography_and_information_assets_as_first_class():
    profile = visual_direction_service.compile_profile("motion_graphics")
    assert "typography" in profile["first_class_assets"]
    assert "data_visualization" in profile["first_class_assets"]
    assert "typography" in profile["qa_dimensions"]


def test_cartoon_profile_prioritizes_identity_and_style_consistency():
    profile = visual_direction_service.compile_profile("cartoon")
    assert "character_identity" in profile["qa_dimensions"]
    assert "style_consistency" in profile["qa_dimensions"]


def test_canonical_production_profile_catalog_is_complete_and_provider_independent():
    expected = {"cinematic", "commercial", "documentary", "educational", "explainer", "cartoon", "animation", "3d_stylized", "motion_graphics", "social_short", "product_film", "corporate_film", "story_narrative", "news_informative", "photoreal", "social_post", "long_form", "custom"}
    profiles = visual_direction_service.production_profiles()
    assert {item["profile_id"] for item in profiles} == expected
    assert all(item["provider_independent"] is True for item in profiles)
    assert all(item["planning_only"] is True for item in profiles)
    assert all(item["digest"] for item in profiles)


def test_profile_digest_is_deterministic():
    a = visual_direction_service.compile_profile("cinematic", task_type="commercial")
    b = visual_direction_service.compile_profile("cinematic", task_type="commercial")
    assert a["digest"] == b["digest"]
