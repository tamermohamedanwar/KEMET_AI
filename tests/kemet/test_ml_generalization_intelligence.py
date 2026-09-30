from app.services.ml_generalization_intelligence import ml_generalization_intelligence


def test_svm_assessment_is_governed_and_generalization_focused():
    result = ml_generalization_intelligence.assess_svm()
    assert result["schema"] == "kemet.ml.generalization_assessment.v1"
    assert "generalization" in result["generalization_focus"]
    assert "hyperparameter_selection_without_test_leakage" in result["evaluation_requirements"]
    assert result["governance"]["auto_train"] is False
    assert len(result["digest"]) == 64


def test_generalization_gap_is_advisory():
    result = ml_generalization_intelligence.compare_signal(train_score=0.98, test_score=0.70)
    assert result["status"] == "generalization_gap_review_required"
    assert result["execution_authority"] == "none"


def test_low_test_score_is_not_called_overfit_without_gap():
    result = ml_generalization_intelligence.compare_signal(train_score=0.48, test_score=0.44)
    assert result["status"] == "underfit_or_signal_insufficient_review_required"


def test_invalid_task_fails_closed():
    try:
        ml_generalization_intelligence.assess_svm(task="deployment")
    except ValueError as exc:
        assert str(exc) == "unsupported_ml_task"
    else:
        raise AssertionError("invalid task must fail closed")
