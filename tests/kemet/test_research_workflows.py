from app.core.federation.research_workflows import ResearchWorkflowService


def test_workflow_catalog_contains_core_business_research_surfaces():
    catalog = ResearchWorkflowService().catalog()
    ids = {item["workflow_id"] for item in catalog}
    assert ids == {"market_intelligence", "competitor_radar", "customer_voice", "trend_radar"}


def test_workflow_prepare_is_governed_and_uses_multiple_sources():
    result = ResearchWorkflowService().prepare(
        "market_intelligence",
        "market size, demand, pricing and competitors",
    )
    assert result["plan"]["source_count"] >= 2
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["auto_execute"] is False


def test_workflow_run_builds_review_gated_decision_record():
    class FakeEngine:
        def run(self, question, **kwargs):
            return {
                "claims": [{"claim_id": "c1", "text": "Demand increased.", "source_id": "web_search", "locator": "https://example.com", "confidence": 0.9}],
                "sources": [{"source_id": "web_search", "locator": "https://example.com", "title": "Example", "confidence": 0.9}],
                "corroboration": [], "contradictions": [], "errors": [],
                "evidence_package": {"digest": "e" * 64},
                "governance": {"read_only": True, "external_execution": False, "database_mutation": False, "auto_execute": False},
            }
        def synthesize(self, result):
            return {"status": "evidence_available", "confidence": 0.9, "source_count": 1, "claim_count": 1, "corroborated_count": 0, "contradiction_count": 0, "decision_readiness": "ready_for_business_review", "recommendation_policy": "review"}
    result = ResearchWorkflowService(engine=FakeEngine()).run("market_intelligence", "demand", task_id="task-2", organization_id=7)
    assert result["decision_record"]["status"] == "review_required"
    assert result["governance"]["decision_digest"] == result["decision_record"]["digest"]


def test_unknown_workflow_fails_closed():
    try:
        ResearchWorkflowService().prepare("unknown", "anything")
    except ValueError as exc:
        assert str(exc) == "unsupported_research_workflow"
    else:
        raise AssertionError("unsupported workflow must fail closed")
