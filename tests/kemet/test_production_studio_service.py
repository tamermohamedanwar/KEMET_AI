from app.services.production_studio_service import ProductionStudioService


def test_production_plan_is_end_to_end_and_approval_gated():
    plan = ProductionStudioService().plan(
        organization_id=1,
        title="Mendes Episode",
        platforms=["youtube", "tiktok"],
        reference_uri="https://example.test/reference",
    )
    assert plan["plan_digest"]
    assert [x["stage"] for x in plan["stages"]] == [
        "research", "script", "visuals", "motion", "voice", "edit", "review", "distribution"
    ]
    assert plan["reference"]["provided"] is True
    assert plan["execution"]["automatic"] is False
    assert plan["execution"]["canonical_runtime_only"] is True
    assert plan["governance"]["human_approval_required"] is True


def test_production_plan_does_not_expose_execution_authority():
    plan = ProductionStudioService().plan(organization_id=1, title="Test")
    assert plan["governance"]["external_execution"] is False
    assert plan["governance"]["database_mutation"] is False
    for stage in plan["stages"]:
        assert "tool_recommendations" in stage
