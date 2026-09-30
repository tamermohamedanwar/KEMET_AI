import hashlib
import pytest

from app.services.ml_evaluation_evidence_service import ml_evaluation_evidence_service

DIGEST = hashlib.sha256(b"dataset-v1").hexdigest()


def evidence(**overrides):
    value = {
        "leakage_evidence": {"status": "passed", "method": "feature_boundary_review"},
        "generalization_evidence": {"validation_strategy": "train_validation_test", "gap": 0.05},
        "error_analysis": {"out_of_sample": {"summary": "reviewed"}},
        "provenance": {"source": "authorized_benchmark", "dataset_digest": DIGEST},
    }
    value.update(overrides)
    return value


def test_builds_complete_evidence_package():
    result = ml_evaluation_evidence_service.build(
        organization_id=1, task_id="task-1", dataset_digest=DIGEST,
        baseline={"metric": "f1", "value": 0.42},
        model_results=[{"model": "svm", "f1": 0.71}], **evidence()
    )
    assert result["status"] == "evidence_complete_review_required"
    assert result["governance"]["execution_authority"] == "none"
    assert len(result["evidence_digest"]) == 64


@pytest.mark.parametrize("field,error", [
    ("baseline", "baseline_evidence_required"),
    ("model_results", "model_results_evidence_required"),
    ("leakage_evidence", "leakage_evidence_required"),
    ("generalization_evidence", "generalization_evidence_required"),
    ("error_analysis", "error_analysis_required"),
])
def test_incomplete_evidence_fails_closed(field, error):
    kwargs = evidence()
    kwargs[field] = {} if field != "model_results" else []
    call = {
        "organization_id": 1, "task_id": "task-1", "dataset_digest": DIGEST,
        "baseline": {"metric": "f1"}, "model_results": [{"model": "svm"}], **kwargs
    }
    call[field] = {} if field != "model_results" else []
    with pytest.raises(ValueError, match=error):
        ml_evaluation_evidence_service.build(**call)


def test_leakage_failure_is_not_treated_as_complete():
    bad = evidence(leakage_evidence={"status": "failed", "method": "review"})
    with pytest.raises(ValueError, match="leakage_evidence_incomplete"):
        ml_evaluation_evidence_service.build(
            organization_id=1, task_id="task-1", dataset_digest=DIGEST,
            baseline={"metric": "f1"}, model_results=[{"model": "svm"}], **bad
        )


def test_provenance_digest_is_bound():
    bad = evidence(provenance={"source": "x", "dataset_digest": "b" * 64})
    with pytest.raises(ValueError, match="provenance_dataset_digest_mismatch"):
        ml_evaluation_evidence_service.build(
            organization_id=1, task_id="task-1", dataset_digest=DIGEST,
            baseline={"metric": "f1"}, model_results=[{"model": "svm"}], **bad
        )
