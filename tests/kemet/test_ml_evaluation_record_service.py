import pytest

from app.services.ml_evaluation_record_service import ml_evaluation_record_service


DATASET_DIGEST = "a" * 64


def _record(**overrides):
    value = {
        "organization_id": 1,
        "task_id": "ml-task-001",
        "dataset_digest": DATASET_DIGEST,
        "split_strategy": "train_validation_test",
        "baseline": {"model": "logistic_regression", "f1": 0.62},
        "model_results": [
            {"model": "linear_svm", "f1": 0.68},
            {"model": "rbf_svm", "f1": 0.70},
        ],
        "leakage_check": "passed",
        "generalization": {"train_f1": 0.78, "test_f1": 0.70, "gap": 0.08},
        "provenance": {"source": "governed_benchmark"},
    }
    value.update(overrides)
    return value


def test_record_is_tenant_bound_and_review_gated():
    result = ml_evaluation_record_service.build(**_record())
    assert result["schema"] == "kemet.ml.evaluation_record.v1"
    assert result["organization_id"] == 1
    assert result["status"] == "review_required"
    assert result["governance"]["auto_deploy"] is False
    assert len(result["digest"]) == 64
    assert len(result["evidence_digest"]) == 64


def test_control_chain_keeps_approval_and_execution_pending():
    result = ml_evaluation_record_service.build(**_record())
    chain = ml_evaluation_record_service.control_chain(result)
    assert [stage["stage"] for stage in chain["stages"]] == ["decision", "approval", "execution", "evidence", "learning"]
    assert chain["stages"][1]["status"] == "pending"
    assert chain["stages"][2]["status"] == "not_executed"


def test_invalid_dataset_digest_fails_closed():
    with pytest.raises(ValueError, match="dataset_digest_required"):
        ml_evaluation_record_service.build(**_record(dataset_digest="bad"))


def test_invalid_split_strategy_fails_closed():
    with pytest.raises(ValueError, match="unsupported_split_strategy"):
        ml_evaluation_record_service.build(**_record(split_strategy="random_magic"))
