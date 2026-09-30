import hashlib

import pytest

from app.services.ml_dataset_authorization_service import MLDatasetAuthorizationService


def _service():
    return MLDatasetAuthorizationService()


def _kwargs():
    return dict(
        organization_id=1,
        dataset_id="ds-demo-001",
        owner="business-owner",
        purpose="lead_conversion_evaluation",
        allowed_use="evaluation",
        sensitivity_classification="internal",
        source="authorized_business_export",
        dataset_sha256=hashlib.sha256(b"authorized-dataset").hexdigest(),
        authorization_reference="AUTH-2026-001",
        human_review_status="approved",
    )


def test_authorized_record_is_tenant_bound_and_human_reviewed():
    record = _service().authorize(**_kwargs())
    assert record["schema"] == "kemet.ml.dataset_authorization.v1"
    assert record["status"] == "authorized"
    assert record["organization_id"] == 1
    assert record["governance"]["execution_authority"] == "none"
    assert MLDatasetAuthorizationService.can_enter_evaluation(record)
    assert len(record["digest"]) == 64


def test_pending_review_cannot_enter_evaluation():
    data = _kwargs()
    data["human_review_status"] = "pending"
    record = _service().authorize(**data)
    assert record["status"] == "pending_review"
    assert not MLDatasetAuthorizationService.can_enter_evaluation(record)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("allowed_use", "deployment", "unsupported_allowed_use"),
        ("sensitivity_classification", "secret", "unsupported_sensitivity_classification"),
        ("dataset_sha256", "abc", "invalid_dataset_digest"),
    ],
)
def test_fail_closed_vocabulary_and_digest(field, value, error):
    data = _kwargs()
    data[field] = value
    with pytest.raises(ValueError, match=error):
        _service().authorize(**data)


def test_missing_authorization_reference_is_blocked():
    data = _kwargs()
    data["authorization_reference"] = ""
    with pytest.raises(ValueError, match="missing_required_authorization_field"):
        _service().authorize(**data)


def test_tenant_mismatch_cannot_enter_evaluation():
    record = _service().authorize(**_kwargs())
    assert not MLDatasetAuthorizationService.can_enter_evaluation(record, organization_id=2)
    assert MLDatasetAuthorizationService.can_enter_evaluation(record, organization_id=1)
