import pytest

from app.core.data_boundary import (
    DataBoundary,
    DataBoundaryError,
    DataEntitlement,
)


def entitlement(**overrides):
    values = {
        "provider_id": "internal",
        "dataset": "sales",
        "organization_id": 7,
        "allowed_operations": ("read",),
    }
    values.update(overrides)
    return DataEntitlement(**values)


def test_boundary_returns_minimum_context_and_evidence():
    context = DataBoundary().resolve(
        organization_id=7,
        user_id=11,
        task_id="task-1",
        provider_id="internal",
        dataset="sales",
        operation="read",
        entitlement=entitlement(),
        source={"revenue": 100, "customer_name": "hidden", "locator": "row:4"},
        fields=("revenue",),
    )

    assert context.values == {"revenue": 100}
    assert context.evidence[0].locator == "row:4"
    assert context.fingerprint()


def test_boundary_fails_closed_on_tenant_mismatch():
    with pytest.raises(DataBoundaryError, match="tenant_mismatch"):
        DataBoundary().resolve(
            organization_id=8,
            user_id=11,
            task_id="task-1",
            provider_id="internal",
            dataset="sales",
            operation="read",
            entitlement=entitlement(),
            source={"revenue": 100},
            fields=("revenue",),
        )


def test_boundary_denies_unentitled_operation():
    with pytest.raises(DataBoundaryError, match="operation_not_entitled"):
        DataBoundary().resolve(
            organization_id=7,
            user_id=11,
            task_id="task-1",
            provider_id="internal",
            dataset="sales",
            operation="export",
            entitlement=entitlement(),
            source={"revenue": 100},
            fields=("revenue",),
        )


def test_boundary_denies_model_use_when_entitlement_disallows_it():
    with pytest.raises(DataBoundaryError, match="model_use_not_allowed"):
        DataBoundary().resolve(
            organization_id=7,
            user_id=11,
            task_id="task-1",
            provider_id="internal",
            dataset="sales",
            operation="read",
            entitlement=entitlement(model_use_allowed=False),
            source={"revenue": 100},
            fields=("revenue",),
        )


def test_boundary_redacts_secret_values_before_model_use():
    context = DataBoundary().resolve(
        organization_id=7,
        user_id=11,
        task_id="task-secret",
        provider_id="internal",
        dataset="sales",
        operation="read",
        entitlement=entitlement(),
        source={"notes": "Authorization: Bearer super-secret", "locator": "row:5"},
        fields=("notes",),
    )
    assert "super-secret" not in context.values["notes"]
    assert "[REDACTED]" in context.values["notes"]


def test_boundary_never_leaks_secret_metadata():
    context = DataBoundary().resolve(
        organization_id=7,
        user_id=11,
        task_id="task-1",
        provider_id="internal",
        dataset="sales",
        operation="read",
        entitlement=entitlement(),
        source={"revenue": 100, "locator": "row:4"},
        fields=("revenue",),
    )
    evidence = context.evidence[0].as_dict()
    assert "api_key" not in evidence["metadata"]
