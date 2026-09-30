import pytest
import hashlib

from app.services.ml_dataset_authorization_service import MLDatasetAuthorizationService
from app.services.ml_evaluation_capability import ml_evaluation_capability


def _kwargs():
    return {
        "organization_id": 1,
        "task_id": "ml-task-001",
        "dataset_digest": hashlib.sha256(b"dataset-v1").hexdigest(),
        "split_strategy": "train_validation_test",
        "baseline": {"model": "majority_class", "f1": 0.42},
        "model_results": [{"model": "linear_svm", "f1": 0.71}],
        "leakage_check": "passed",
        "generalization": {"train_f1": 0.76, "test_f1": 0.71, "gap": 0.05},
        "provenance": {"source": "local_benchmark_fixture"},
    }


def test_capability_is_governed_and_read_only():
    snapshot = ml_evaluation_capability.snapshot()
    assert snapshot["capability_id"] == "ml_evaluation"
    assert snapshot["execution_authority"] == "none"
    assert snapshot["governance"]["human_review_required"] is True
    assert snapshot["governance"]["auto_deploy"] is False


def test_capability_emits_record_and_control_chain():
    result = ml_evaluation_capability.evaluate_record(**_kwargs())
    assert result["record"]["schema"] == "kemet.ml.evaluation_record.v1"
    assert result["record"]["status"] == "review_required"
    stages = result["control_chain"]["stages"]
    assert [stage["stage"] for stage in stages] == ["decision", "approval", "execution", "evidence", "learning"]
    assert stages[2]["status"] == "not_executed"


def test_authorized_dataset_gate_binds_authorization_evidence():
    dataset_digest = hashlib.sha256(b"dataset-v1").hexdigest()
    authorization = MLDatasetAuthorizationService().authorize(
        organization_id=1,
        dataset_id="ds-001",
        owner="business-owner",
        purpose="lead_conversion_evaluation",
        allowed_use="evaluation",
        sensitivity_classification="internal",
        source="authorized_business_export",
        dataset_sha256=dataset_digest,
        authorization_reference="AUTH-2026-001",
        human_review_status="approved",
    )
    result = ml_evaluation_capability.evaluate_authorized_record(
        authorization_record=authorization,
        organization_id=1,
        task_id="ml-authorized-001",
        dataset_digest=dataset_digest,
        split_strategy="train_validation_test",
        baseline={"model": "majority_class", "f1": 0.42},
        model_results=[{"model": "linear_svm", "f1": 0.71}],
        leakage_check="passed",
        generalization={"train_f1": 0.76, "test_f1": 0.71, "gap": 0.05},
    )
    provenance = result["record"]["provenance"]["dataset_authorization"]
    assert provenance["authorization_reference"] == "AUTH-2026-001"
    assert provenance["authorization_digest"] == authorization["digest"]


def test_unauthorized_dataset_cannot_enter_evaluation():
    dataset_digest = hashlib.sha256(b"dataset-v1").hexdigest()
    authorization = MLDatasetAuthorizationService().authorize(
        organization_id=1,
        dataset_id="ds-001",
        owner="business-owner",
        purpose="lead_conversion_evaluation",
        allowed_use="evaluation",
        sensitivity_classification="internal",
        source="authorized_business_export",
        dataset_sha256=dataset_digest,
        authorization_reference="AUTH-2026-001",
        human_review_status="pending",
    )
    import pytest
    with pytest.raises(ValueError, match="ml_dataset_authorization_required"):
        ml_evaluation_capability.evaluate_authorized_record(
            authorization_record=authorization,
            organization_id=1,
            task_id="ml-blocked-001",
            dataset_digest=dataset_digest,
            split_strategy="train_validation_test",
            baseline={},
            model_results=[],
            leakage_check="not_run",
            generalization={},
        )


def test_evaluate_intake_binds_authorized_intake_to_evaluation():
    from app.services.ml_dataset_authorization_service import MLDatasetAuthorizationService
    from app.services.ml_dataset_intake_service import ml_dataset_intake_service

    authorization = MLDatasetAuthorizationService().authorize(
        organization_id=1, dataset_id="ds-001", owner="owner",
        purpose="evaluation", allowed_use="evaluation",
        sensitivity_classification="internal", source="authorized_source",
        dataset_sha256="a" * 64, authorization_reference="AUTH-INTAKE",
        human_review_status="approved",
    )
    intake = ml_dataset_intake_service.build_authorized_intake(
        authorization_record=authorization, organization_id=1,
        dataset_id="ds-001", dataset_digest="a" * 64,
        row_count=100, feature_count=8, target="outcome",
        task_id="task-intake", business_task="predict outcome",
    )
    result = ml_evaluation_capability.evaluate_intake(
        intake_record=intake, authorization_record=authorization,
        split_strategy="train_validation_test", baseline={"metric": "accuracy", "value": 0.5},
        model_results=[{"model": "baseline", "accuracy": 0.5}],
        leakage_check="passed", generalization={"status": "review_required"},
    )
    assert result["record"]["task_id"] == "task-intake"
    assert result["record"]["provenance"]["dataset_intake"]["digest"] == intake["digest"]
    assert result["record"]["provenance"]["dataset_authorization"]["authorization_reference"] == "AUTH-INTAKE"
    assert result["record"]["governance"]["auto_deploy"] is False


def test_evaluate_intake_fails_on_authorization_reference_mismatch():
    from app.services.ml_dataset_authorization_service import MLDatasetAuthorizationService
    from app.services.ml_dataset_intake_service import ml_dataset_intake_service

    authorization = MLDatasetAuthorizationService().authorize(
        organization_id=1, dataset_id="ds-001", owner="owner",
        purpose="evaluation", allowed_use="evaluation",
        sensitivity_classification="internal", source="authorized_source",
        dataset_sha256="a" * 64, authorization_reference="AUTH-REAL",
        human_review_status="approved",
    )
    intake = ml_dataset_intake_service.build_authorized_intake(
        authorization_record=authorization, organization_id=1,
        dataset_id="ds-001", dataset_digest="a" * 64,
        row_count=100, feature_count=8, target="outcome",
        task_id="task-intake", business_task="predict outcome",
    )
    intake["authorization_reference"] = "AUTH-OTHER"
    with pytest.raises(ValueError, match="ml_authorization_reference_mismatch"):
        ml_evaluation_capability.evaluate_intake(
            intake_record=intake, authorization_record=authorization,
            split_strategy="train_validation_test", baseline={}, model_results=[],
            leakage_check="not_run", generalization={},
        )


def test_complete_evaluation_binds_evidence_and_stays_review_gated():
    from app.services.ml_dataset_authorization_service import MLDatasetAuthorizationService
    digest = hashlib.sha256(b"dataset-complete").hexdigest()
    authorization = MLDatasetAuthorizationService().authorize(
        organization_id=1, dataset_id="ds-complete", owner="owner",
        purpose="evaluation", allowed_use="evaluation",
        sensitivity_classification="internal", source="authorized_source",
        dataset_sha256=digest, authorization_reference="AUTH-COMPLETE",
        human_review_status="approved",
    )
    evidence = {
        "leakage_evidence": {"status": "passed", "method": "boundary_review"},
        "generalization_evidence": {"validation_strategy": "train_validation_test", "gap": 0.04},
        "error_analysis": {"out_of_sample": {"summary": "reviewed"}},
        "provenance": {"source": "authorized_benchmark", "dataset_digest": digest},
    }
    result = ml_evaluation_capability.evaluate_complete_record(
        authorization_record=authorization, evidence=evidence,
        organization_id=1, task_id="task-complete", dataset_digest=digest,
        split_strategy="train_validation_test", baseline={"metric": "f1", "value": 0.42},
        model_results=[{"model": "svm", "f1": 0.71}], leakage_check="passed",
        generalization={"train_f1": 0.75, "test_f1": 0.71, "gap": 0.04},
    )
    assert result["evidence_completion"]["status"] == "evidence_complete_review_required"
    assert len(result["record"]["evidence_completion_digest"]) == 64
    assert result["record"]["status"] == "evidence_complete_review_required"
    assert result["record"]["governance"]["auto_deploy"] is False
    assert result["control_chain"]["stages"][2]["status"] == "not_executed"
