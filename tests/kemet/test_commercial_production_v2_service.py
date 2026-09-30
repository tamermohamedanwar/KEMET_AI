from app.services.commercial_production_v2_service import commercial_production_v2_service


def test_commercial_v2_compiles_canonical_seven_shot_graph():
    result = commercial_production_v2_service.build(organization_id=1)
    assert result["schema"] == "kemet.commercial.production_v2.v1"
    assert len(result["creative"]["shots"]) == 7
    assert result["creative"]["duration_seconds"] == 45
    assert result["production_graph"]["canonical"] is True
    assert result["production_graph"]["governance"]["external_execution"] is False
    assert result["governance"]["execution_authority"] is False
    assert result["governance"]["mcp"] is False


def test_commercial_v2_fails_quality_readiness_without_real_evidence():
    result = commercial_production_v2_service.build(organization_id=1)
    readiness = result["quality_readiness"]
    assert readiness["status"] == "BLOCKED"
    assert readiness["production_ready"] is False
    assert result["truth_boundary"]["artifact_verified"] is False
    assert result["truth_boundary"]["revenue_verified"] is False


def test_commercial_v2_preserves_revenue_lifecycle_and_post_composited_ui():
    result = commercial_production_v2_service.build(
        organization_id=7,
        project_id="commercial-v2-test",
        language="ar-EG",
        platforms=["youtube", "telegram"],
    )
    assert result["revenue_path"]["lifecycle"] == [
        "content", "distribution", "audience_leads", "offer",
        "payment", "fulfillment", "profit", "measurement", "learning",
    ]
    assert result["production_graph"]["prompts_are_derived"] is True
    assert result["creative"]["shots"][0]["visual_rule"].find("composited in post") >= 0


def test_commercial_v2_rejects_invalid_tenant():
    try:
        commercial_production_v2_service.build(organization_id=0)
    except ValueError as exc:
        assert str(exc) == "organization_required"
    else:
        raise AssertionError("expected organization validation")


def test_commercial_v2_binds_cinematic_profile_into_planning_and_quality_gate():
    from app.services.commercial_production_v2_service import commercial_production_v2_service
    result = commercial_production_v2_service.build(organization_id=7, project_id="commercial-profile-1")
    profile = result["production_profile"]
    assert profile["profile_id"] == "cinematic"
    assert result["planning_projection"]["specification"]["production_profile"]["digest"] == profile["digest"]
    assert result["quality_readiness"]["production_profile"]["digest"] == profile["digest"]
    assert any(item["gate"] == "camera" for item in result["quality_readiness"]["profile_checks"])
    assert result["planning_projection"]["planning_only"] is True
    assert result["governance"]["execution_authority"] is False
