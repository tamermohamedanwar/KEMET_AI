from app import create_app
from app.services.evaluation_learning import EvaluationLearningService


def _lifecycle(**overrides):
    value = {
        "decision_id": "d-1",
        "capability_id": "kemet.business_insights",
        "state": "outcome_observed",
        "approval": {"id": 10, "status": "approved"},
        "execution": {"id": 11, "status": "completed"},
        "observed_outcome": [{"metric": "paid_amount", "change": 10}],
        "governance": {
            "read_only": True,
            "external_execution": False,
            "database_mutation": False,
        },
    }
    value.update(overrides)
    return value


def test_evaluation_passes_for_completed_observed_lifecycle():
    result = EvaluationLearningService.evaluate(_lifecycle())
    assert result["success"] is True
    assert result["status"] == "pass"
    assert result["score"] == 100
    assert result["quality_dimensions"]["decision_quality"] is True
    assert result["quality_dimensions"]["approval_quality"] is True
    assert result["quality_dimensions"]["execution_quality"] is True
    assert result["quality_dimensions"]["measurement_quality"] is True
    assert result["quality_dimensions"]["outcome_signal"] is True


def test_evaluation_fails_closed_on_governance_violation():
    lifecycle = _lifecycle(governance={"read_only": False})
    result = EvaluationLearningService.evaluate(lifecycle)
    assert result["success"] is True
    assert result["status"] == "fail"
    assert result["governance"]["policy_mutation"] is False


def test_evaluation_reviews_missing_outcome():
    lifecycle = _lifecycle(state="executed", observed_outcome=[])
    result = EvaluationLearningService.evaluate(lifecycle)
    assert result["status"] == "review"
    assert result["checks"]["outcome"] is False


def test_learning_summary_is_non_mutating():
    result = EvaluationLearningService.build([
        _lifecycle(),
        _lifecycle(
            decision_id="d-2",
            state="rejected",
            approval={"id": 12, "status": "rejected"},
            execution={"id": None, "status": None},
            observed_outcome=[],
        ),
    ])
    assert result["success"] is True
    assert result["summary"]["decisions"] == 2
    assert result["summary"]["outcome_observation_rate"] == 0.5
    assert result["summary"]["quality_dimensions"]["decision_quality"] == 1.0
    assert result["summary"]["quality_dimensions"]["measurement_quality"] == 0.5
    assert result["governance"]["read_only"] is True
    assert result["governance"]["policy_mutation"] is False
    assert result["learning_signals"]


def test_learning_loop_route_registered():
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/dashboard/api/bos/learning-loop" in routes
