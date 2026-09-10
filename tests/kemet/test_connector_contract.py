from app.core.integration.connector_contract import ConnectorContract


def test_high_risk_connector_requires_governance_controls():
    contract = ConnectorContract(
        connector_id="whatsapp",
        organization_id=1,
        operations=("send_message",),
        data_scopes=("customer_contact",),
        risk_tier="high",
        approval_level="human",
        evidence_required=True,
        attestation_required=False,
    )
    assert contract.validate()["valid"] is True
    assert contract.allows("send_message", 1) is True
    assert contract.allows("send_message", 2) is False


def test_critical_connector_requires_attestation():
    contract = ConnectorContract(
        connector_id="payments",
        organization_id=1,
        operations=("refund",),
        risk_tier="critical",
        approval_level="human_critical",
        evidence_required=True,
        attestation_required=False,
    )
    result = contract.validate()
    assert result["valid"] is False
    assert "critical_requires_attestation" in result["errors"]


def test_connector_scope_is_explicit():
    contract = ConnectorContract(
        connector_id="telegram",
        organization_id=7,
        operations=("send_message", "read_message"),
        data_scopes=("messages",),
        risk_tier="medium",
        approval_level="human",
    )
    payload = contract.as_dict()
    assert payload["organization_id"] == 7
    assert payload["operations"] == ["send_message", "read_message"]
    assert payload["data_scopes"] == ["messages"]


def test_connector_registry_isolated_by_organization():
    from app.core.integration.connector_registry import ConnectorRegistry

    registry = ConnectorRegistry()
    first = ConnectorContract(
        connector_id="whatsapp",
        organization_id=1,
        operations=("send_message",),
        risk_tier="high",
        approval_level="human",
        evidence_required=True,
    )
    second = ConnectorContract(
        connector_id="whatsapp",
        organization_id=2,
        operations=("read_message",),
        risk_tier="medium",
        approval_level="human",
    )
    assert registry.register(first)["registered"] is True
    assert registry.register(second)["registered"] is True
    assert registry.allows("whatsapp", "send_message", 1) is True
    assert registry.allows("whatsapp", "send_message", 2) is False
    assert registry.allows("whatsapp", "read_message", 2) is True
    assert len(registry.list_for_organization(1)) == 1
    assert len(registry.list_for_organization(2)) == 1
