from app.services.agentic_engineering_service import agentic_engineering_service


def test_external_agent_contract_cannot_be_executor():
    result = agentic_engineering_service.contract(
        agent_id="research.specialist",
        provider_id="external-provider",
        kind="research",
        capabilities={"research", "proposal"},
        authority="governed_submission",
    )
    assert result["execution_authority"] is False
    assert result["authority"] == "governed_submission"
    assert result["governance"]["canonical_executor"] == "kemet"


def test_kemet_executor_contract_is_explicit():
    result = agentic_engineering_service.contract(
        agent_id="kemet.runtime",
        provider_id="kemet",
        kind="execution_specialist",
        capabilities={"execute"},
        authority="canonical_executor",
        execution_authority=True,
    )
    assert result["execution_authority"] is True
    assert result["authority"] == "canonical_executor"
    assert result["requires_human_approval"] is False


def test_lifecycle_evaluation_fails_without_governance():
    result = agentic_engineering_service.evaluate({
        "decision_id": "d-1",
        "capability_id": "revenue",
        "state": "reviewed",
        "governance": {"read_only": False, "external_execution": True, "database_mutation": True},
    })
    assert result["success"] is True
    assert result["status"] == "fail"
    assert result["checks"]["governance"] is False


def test_observability_exposes_business_trace_without_execution():
    lifecycle = {
        "decision_id": "d-2",
        "capability_id": "revenue",
        "state": "outcome_observed",
        "context": {"lead_id": 6},
        "plan": {"steps": 3},
        "proposal": {"action": "sales_follow_up"},
        "approval": {"id": 7, "status": "approved"},
        "execution": {"status": "completed"},
        "evidence": {"payment_id": 12},
        "observed_outcome": [{"type": "payment", "recorded": True}],
        "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
    }
    result = agentic_engineering_service.observability(lifecycle=lifecycle)
    assert result["evaluation"]["status"] == "pass"
    assert all(result["trace"].values())
    assert result["governance"]["external_execution"] is False


def test_batch_evaluation_returns_learning_signals():
    result = agentic_engineering_service.evaluation_batch([{
        "decision_id": "d-3",
        "capability_id": "revenue",
        "state": "rejected",
        "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
        "approval": {"status": "rejected"},
        "execution": {"status": None},
    }])
    assert result["success"] is True
    assert result["summary"]["rejection_rate"] == 1.0
    assert result["learning_signals"]
