from app.core.response_contract import ResponseContract


def test_response_contract_is_action_first_and_bounded():
    contract = ResponseContract()
    rules = contract.system_rules()
    assert contract.lead_with_action is True
    assert contract.max_list_items == 5
    assert "start with the action or answer" in rules
    assert "Suppress tangents" in rules
    assert "Never claim execution" in rules
