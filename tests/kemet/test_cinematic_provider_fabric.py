from app.services.cinematic_provider_fabric import cinematic_provider_fabric


def test_provider_fabric_keeps_external_execution_governed():
    snapshot = cinematic_provider_fabric.snapshot(1)
    assert snapshot["governance"]["external_execution"] is False
    assert snapshot["governance"]["execution_authority"] is False
    assert snapshot["governance"]["mcp"] is False


def test_provider_fabric_builds_jobs_from_canonical_shots():
    cinematic = {
        "shots": [{
            "shot_id": "s1-sh1",
            "action": "A character enters a room.",
            "emotion": "curiosity",
            "camera": "medium",
            "lens": "35mm",
            "framing": "balanced",
            "movement": "slow push",
            "lighting": "warm",
            "time": "evening",
            "dialogue": "Hello.",
            "reference_asset_ids": ["character-ref-1"],
            "character_bindings": [{"id": "character-1", "version": 1, "digest": "abc"}],
            "world_binding": {"id": "world-1", "version": 1, "digest": "def"},
        }]
    }
    result = cinematic_provider_fabric.build_episode_jobs(
        organization_id=1,
        cinematic=cinematic,
        episode_id="s1e1",
    )
    assert result["success"] is True
    job = result["fabric"]["jobs"][0]
    assert job["image"]["request"]["prompt_source"] == "kemet_canonical_binding"
    assert job["image"]["request"]["reference_inputs"] == ["character-ref-1"]
    assert result["fabric"]["approval"]["status"] == "pending"

def test_video_preflight_exposes_non_google_backend_candidate():
    result = cinematic_provider_fabric.provider_preflight()
    candidates = {item["provider_id"] for item in result["video_candidates"]}
    assert "google_veo_3_1" in candidates
    assert "wan2_2_remote" in candidates
    wan = next(item for item in result["video_candidates"] if item["provider_id"] == "wan2_2_remote")
    assert wan["execution_authority"] is False
    assert wan["external_execution"] is False
    assert wan["mcp"] is False


def test_real_veo_provider_preflight_is_explicit():
    result = cinematic_provider_fabric.provider_preflight()
    assert result["video"]["provider_id"] == "google_veo_3_1"
    assert result["video"]["model"] == "veo-3.1-generate-preview"
    assert result["video"]["execution_authority"] is False


def test_real_provider_cannot_execute_without_human_approval():
    shot = {
        "shot_id": "s1-sh1",
        "canonical_shot_digest": "canonical-digest",
        "provider_prompt": "derived prompt",
    }
    try:
        cinematic_provider_fabric.execute_approved_video_shot(
            organization_id=1,
            episode_id="s1e1",
            shot=shot,
            approval={"approved": False, "organization_id": 1, "shot_id": "s1-sh1", "canonical_shot_digest": "canonical-digest"},
            output_path="/tmp/kemet-never-generate.mp4",
        )
    except ValueError as exc:
        assert str(exc) == "human_approval_required"
    else:
        raise AssertionError("provider execution must require approval")


def test_real_provider_binds_approval_to_canonical_shot_digest():
    shot = {
        "shot_id": "s1-sh1",
        "canonical_shot_digest": "canonical-digest",
        "provider_prompt": "derived prompt",
    }
    try:
        cinematic_provider_fabric.execute_approved_video_shot(
            organization_id=1,
            episode_id="s1e1",
            shot=shot,
            approval={"approved": True, "organization_id": 1, "shot_id": "s1-sh1", "canonical_shot_digest": "wrong-digest"},
            output_path="/tmp/kemet-never-generate.mp4",
        )
    except ValueError as exc:
        assert str(exc) == "approval_shot_digest_mismatch"
    else:
        raise AssertionError("provider execution must bind the canonical shot digest")
