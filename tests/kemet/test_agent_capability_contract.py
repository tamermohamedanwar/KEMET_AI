import pytest

from app.core.federation.agent_capability_contract import AgentCapabilityContract
from app.core.federation.specialist_registry import specialist_registry


def test_external_specialist_is_never_a_canonical_executor():
    for provider_id in ("manus", "meta"):
        contract = specialist_registry.capability_contract(provider_id)
        assert contract is not None
        assert contract.execution_authority is False
        assert contract.authority != "canonical_executor"
        assert contract.provider_id != "kemet"


def test_manus_is_governed_submission_specialist():
    contract = specialist_registry.capability_contract("manus")
    assert contract is not None
    assert contract.authority == "governed_submission"
    assert contract.can_submit() is True
    assert contract.requires_human_approval is True
    assert contract.supports_async is True


def test_meta_is_advisory_specialist():
    contract = specialist_registry.capability_contract("meta")
    assert contract is not None
    assert contract.authority == "advisory"
    assert contract.can_submit() is False


def test_contract_rejects_external_execution_authority():
    with pytest.raises(ValueError, match="external_agent_execution_authority_forbidden"):
        AgentCapabilityContract(
            contract_version="1.0", agent_id="evil.executor", provider_id="manus",
            kind="reasoning", authority="canonical_executor", execution_authority=True,
        )
