from app.core.federation.executive_brief import ExecutiveBriefService


def test_executive_brief_is_traceable_and_review_gated():
    service = ExecutiveBriefService()
    result = service.build(
        task_id="t-1", organization_id=7, question="market question",
        research={
            "claims": [{"claim_id": "c1", "text": "Market growth increased", "source_id": "web", "locator": "https://example.com", "confidence": 0.8}],
            "sources": [{"source_id": "web"}], "corroboration": [], "contradictions": [],
            "synthesis": {"status": "evidence_available", "confidence": 0.8},
            "evidence_package": {"digest": "evidence-digest"},
        },
    )
    assert result["type"] == "executive_decision_brief"
    assert result["decision"]["human_review_required"] is True
    assert result["decision"]["auto_execute"] is False
    assert result["traceability"]["research_evidence_digest"] == "evidence-digest"
    assert len(result["digest"]) == 64


def test_executive_brief_fails_closed_on_conflict():
    service = ExecutiveBriefService()
    result = service.build(
        task_id="t-2", organization_id=7, question="risk",
        research={
            "claims": [{"claim_id": "c1", "text": "Risk increased", "source_id": "web", "locator": "https://example.com", "confidence": 0.7}],
            "sources": [{"source_id": "web"}],
            "corroboration": [], "contradictions": [{"claim_key": "risk", "status": "review_required"}],
            "synthesis": {"status": "review_required", "confidence": 0.5},
            "evidence_package": {"digest": "digest"},
        },
    )
    assert result["decision"]["status"] == "review_required"
    assert result["conflicts"]
