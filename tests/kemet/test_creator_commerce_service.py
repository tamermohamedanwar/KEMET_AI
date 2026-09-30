from app.services.creator_commerce_service import creator_commerce_service


def test_high_value_opportunity_is_ranked_without_execution_authority():
    result = creator_commerce_service.build_opportunity(
        topic="best work laptops under 30000",
        audience="Arabic small-business owners",
        demand_score=90,
        competition_score=30,
        commercial_intent="transactional",
        monetization_score=92,
        recommended_format="comparison",
        platforms=["youtube", "tiktok"],
    )
    assert result["opportunity_score"] >= 75
    assert result["recommendation"] == "scale_candidate"
    assert result["governance"]["execution_authority"] is False
    assert result["governance"]["external_execution"] is False


def test_content_plan_requires_approval_and_discloses_affiliate():
    opportunity = creator_commerce_service.build_opportunity(
        topic="best business tools",
        audience="Arabic founders",
        demand_score=80,
        competition_score=40,
        commercial_intent="commercial",
        monetization_score=85,
        recommended_format="review",
        platforms=["youtube", "facebook"],
    )["opportunity"]
    result = creator_commerce_service.build_content_plan(
        organization_id=1,
        opportunity=opportunity,
        language="ar",
    )
    assert result["status"] == "approval_required"
    assert result["content"]["originality_required"] is True
    assert result["content"]["affiliate_disclosure_required"] is True
    assert "affiliate" in result["monetization"]["channels"]
    assert result["governance"]["execution_authority"] is False
    assert all(item["execution_authority"] is False for item in result["distribution"])


def test_invalid_scores_fail_closed():
    for value in (-1, 101, float("nan"), float("inf")):
        try:
            creator_commerce_service.build_opportunity(
                topic="test", demand_score=value, competition_score=20, monetization_score=20,
            )
        except ValueError as exc:
            assert str(exc) == "score_out_of_range"
        else:
            raise AssertionError("invalid score was accepted")
