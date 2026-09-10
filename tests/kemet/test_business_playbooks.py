from app.automation.playbook_engine import playbook_engine


def test_sales_playbook_is_multi_step():
    plan = {
        "intent": "lead_scoring",
        "action": "lead_scoring",
        "parameters": {},
        "confidence": 0.94,
        "expected_result": "Prioritized revenue opportunities.",
    }
    playbook = playbook_engine.build(plan)
    assert [s["action"] for s in playbook["steps"]] == [
        "lead_scoring", "ai_sales_qualification", "revenue_opportunity"
    ]
    assert playbook["steps"][1]["depends_on"] == ["step_1"]
    assert playbook["steps"][2]["condition"] == "previous.success == true"


def test_retention_playbook_contains_governed_follow_up():
    plan = {
        "intent": "customer_retention",
        "action": "customer_retention",
        "parameters": {},
        "confidence": 0.92,
    }
    playbook = playbook_engine.build(plan)
    assert len(playbook["steps"]) == 3
    assert playbook["steps"][-1]["action"] == "sales_follow_up"
    assert playbook["steps"][-1]["policy"]["fail_closed"] is True
    assert playbook["risk"] == "high"
