import pytest

from app.services.ml_dataset_authorization_service import MLDatasetAuthorizationService
from app.services.ml_dataset_intake_service import ml_dataset_intake_service


def approved_authorization(*, organization_id=1, dataset_id="ds-001", digest=None, human_review_status="approved"):
    return MLDatasetAuthorizationService().authorize(
        organization_id=organization_id,
        dataset_id=dataset_id,
        owner="data-owner",
        purpose="model evaluation",
        allowed_use="evaluation",
        sensitivity_classification="internal",
        source="authorized_business_source",
        dataset_sha256=digest or "a" * 64,
        authorization_reference="AUTH-001",
        human_review_status=human_review_status,
    )


def test_dataset_intake_is_tenant_bound_and_review_gated():
    record = ml_dataset_intake_service.assess(
        organization_id=1,
        dataset_id="ds-001",
        dataset_digest="a" * 64,
        row_count=100,
        feature_count=8,
        target="outcome",
        source_type="synthetic_fixture",
    )
    assert record["schema"] == "kemet.ml.dataset_intake.v1"
    assert record["status"] == "review_required"
    assert record["authorized_entry"] is False
    assert record["governance"]["training_authority"] is False
    assert len(record["digest"]) == 64


def test_dataset_intake_rejects_invalid_shape_and_source():
    with pytest.raises(ValueError, match="dataset_shape_required"):
        ml_dataset_intake_service.assess(
            organization_id=1, dataset_id="ds", dataset_digest="a" * 64,
            row_count=0, feature_count=2, target="y"
        )
    with pytest.raises(ValueError, match="unsupported_dataset_source"):
        ml_dataset_intake_service.assess(
            organization_id=1, dataset_id="ds", dataset_digest="a" * 64,
            row_count=2, feature_count=2, target="y", source_type="unknown"
        )


def test_authorized_intake_binds_dataset_authorization_and_task():
    authorization = approved_authorization()
    record = ml_dataset_intake_service.build_authorized_intake(
        authorization_record=authorization,
        organization_id=1,
        dataset_id="ds-001",
        dataset_digest="a" * 64,
        row_count=100,
        feature_count=8,
        target="outcome",
        task_id="task-001",
        business_task="predict customer outcome",
        evaluation_plan={"split": "train_validation_test"},
        generalization_requirements={"out_of_sample_error": True},
    )
    assert record["status"] == "ready_for_governed_evaluation"
    assert record["authorization_reference"] == "AUTH-001"
    assert record["authorization_digest"] == authorization["digest"]
    assert record["task_id"] == "task-001"
    assert record["control_chain"]["execution"] == "not_executed"
    assert record["governance"]["execution_authority"] == "none"


def test_authorized_intake_fails_without_approved_authorization():
    pending = approved_authorization(human_review_status="pending")
    with pytest.raises(ValueError, match="ml_dataset_authorization_required"):
        ml_dataset_intake_service.build_authorized_intake(
            authorization_record=pending,
            organization_id=1,
            dataset_id="ds-001",
            dataset_digest="a" * 64,
            row_count=100,
            feature_count=8,
            target="outcome",
            task_id="task-001",
            business_task="predict customer outcome",
        )


def test_authorized_intake_fails_on_tenant_identity_mismatch():
    authorization = approved_authorization(organization_id=2)
    with pytest.raises(ValueError, match="ml_dataset_authorization_required"):
        ml_dataset_intake_service.build_authorized_intake(
            authorization_record=authorization,
            organization_id=1,
            dataset_id="ds-001",
            dataset_digest="a" * 64,
            row_count=100,
            feature_count=8,
            target="outcome",
            task_id="task-001",
            business_task="predict customer outcome",
        )


def test_authorized_intake_fails_on_dataset_or_digest_mismatch():
    authorization = approved_authorization()
    common = dict(
        authorization_record=authorization,
        organization_id=1,
        row_count=100,
        feature_count=8,
        target="outcome",
        task_id="task-001",
        business_task="predict customer outcome",
    )
    with pytest.raises(ValueError, match="ml_dataset_identity_mismatch"):
        ml_dataset_intake_service.build_authorized_intake(
            **common, dataset_id="other-dataset", dataset_digest="a" * 64
        )
    with pytest.raises(ValueError, match="ml_dataset_digest_mismatch"):
        ml_dataset_intake_service.build_authorized_intake(
            **common, dataset_id="ds-001", dataset_digest="b" * 64
        )


def test_authorized_intake_requires_task_identity():
    authorization = approved_authorization()
    with pytest.raises(ValueError, match="ml_task_identity_required"):
        ml_dataset_intake_service.build_authorized_intake(
            authorization_record=authorization,
            organization_id=1,
            dataset_id="ds-001",
            dataset_digest="a" * 64,
            row_count=100,
            feature_count=8,
            target="outcome",
            task_id=" ",
            business_task="predict customer outcome",
        )
