from app import create_app
from app.services.business_outcome_service import BusinessOutcomeService


def test_business_outcome_requires_organization():
    result = BusinessOutcomeService.build(None)
    assert result["success"] is False
    assert result["error"] == "organization_required"


def test_business_outcome_normalizes_unknown_period():
    app = create_app()
    with app.app_context():
        result = BusinessOutcomeService.build(7, period="365d")
    assert result["success"] is True
    assert result["period"] == "30d"


def test_business_outcome_is_advisory_and_structured():
    app = create_app()
    with app.app_context():
        result = BusinessOutcomeService.build(7, period="30d")

    assert result["success"] is True
    assert result["engine"] == "kemet_outcome"
    assert result["period"] == "30d"
    assert "health_score" in result
    assert "automation" in result
    assert "roi" in result
    assert "next_best_actions" in result
    assert result["governance"]["mode"] == "advisory"
    assert result["governance"]["requires_approval"] is True
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["database_mutation"] is False
