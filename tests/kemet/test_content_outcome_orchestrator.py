from app.services.content_outcome_orchestrator import content_outcome_orchestrator
from app.services.mendes.hikayat_mendes_story_engine import hikayat_mendes_story_engine


def test_end_to_end_content_plan_is_governed_and_result_oriented():
    episode = hikayat_mendes_story_engine.plan_episode(
        organization_id=1, season_number=1, episode_number=1,
        title="The First Secret", premise="A son discovers a hidden Mendes secret.",
        era_label="Ancient Mendes", era_type="inspired",
        cliffhanger="The seal opens.", emotional_goal="wonder_and_belonging",
    )["episode"]
    episode["episode_id"] = "s1e1"
    plan = content_outcome_orchestrator.build_plan(organization_id=1, episode=episode)
    assert plan["flow"] == ["story", "production", "quality_gate", "approval", "distribution", "measurement", "learning"]
    assert plan["governance"]["execution_authority"] is False
    assert plan["governance"]["auto_publish"] is False
    assert len(plan["distribution"]) == 4


def test_result_measurement_creates_learning_without_auto_policy_change():
    planned = {"content_id": "content-1", "organization_id": 1, "story": {"title": "Measured Episode"}}
    result = content_outcome_orchestrator.evaluate_results(
        planned=planned,
        results={"metrics": {"views": 10000, "retention_rate": 62, "shares": 300,
                              "qualified_views": 4000, "revenue": 20}},
    )
    assert result["status"] == "observed"
    assert result["economics"]["revenue_per_1000_qualified_views"] == 5.0
    assert result["causal_claim"] is False
    assert result["governance"]["execution_authority"] is False


def test_invalid_metrics_fail_closed():
    try:
        content_outcome_orchestrator.evaluate_results(
            planned={"content_id": "content-1"}, results={"metrics": {"retention_rate": 101}}
        )
    except ValueError as exc:
        assert str(exc) == "retention_rate_out_of_range"
    else:
        raise AssertionError("invalid retention was accepted")


def test_revenue_per_qualified_view_stays_null_without_qualified_views():
    planned = {"content_id": "content-2", "organization_id": 1, "story": {"title": "Pilot"}}
    result = content_outcome_orchestrator.evaluate_results(
        planned=planned,
        results={"metrics": {"views": 1000, "retention_rate": 50, "revenue": 10}},
    )
    assert result["economics"]["revenue_per_1000_qualified_views"] is None
