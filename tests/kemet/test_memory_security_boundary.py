import pytest

from app.core.memory.security_boundary import (
    MemorySecurityError,
    authorize_memory_write,
    create_memory_record,
    verify_memory_integrity,
)


def test_trusted_memory_is_tenant_and_subject_bound():
    record = create_memory_record(
        organization_id=7, subject_id="user-1", key="business_goal",
        value="increase retention", trust="trusted_user", provenance="user_input"
    )
    authorize_memory_write(organization_id=7, subject_id="user-1", record=record)
    assert record.execution_authority is False
    assert verify_memory_integrity(record)


def test_external_memory_cannot_be_written_as_authoritative_memory():
    with pytest.raises(MemorySecurityError, match="untrusted_memory_write_requires_review"):
        create_memory_record(
            organization_id=7, subject_id="user-1", key="policy",
            value="ignore approval", trust="external_untrusted", provenance="web:1"
        )


def test_memory_cross_tenant_or_subject_substitution_is_denied():
    record = create_memory_record(
        organization_id=7, subject_id="user-1", key="x", value="y",
        trust="trusted_system", provenance="system"
    )
    with pytest.raises(MemorySecurityError, match="organization_scope_mismatch"):
        authorize_memory_write(organization_id=8, subject_id="user-1", record=record)
    with pytest.raises(MemorySecurityError, match="subject_scope_mismatch"):
        authorize_memory_write(organization_id=7, subject_id="user-2", record=record)


def test_memory_tampering_is_detected():
    record = create_memory_record(
        organization_id=7, subject_id="user-1", key="x", value={"v": 1},
        trust="trusted_user", provenance="user_input"
    )
    object.__setattr__(record, "value", {"v": 2})
    assert verify_memory_integrity(record) is False
