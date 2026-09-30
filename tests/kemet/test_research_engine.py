from app.core.federation.research_engine import ResearchEngine, ResearchSource


def test_research_plan_selects_multiple_sources():
    engine = ResearchEngine()
    plan = engine.plan("market competitor trend and customer reviews")
    assert plan["source_count"] >= 2
    assert "web_search" in plan["sources"]


def test_research_engine_deduplicates_extracts_and_binds_evidence():
    engine = ResearchEngine()
    source = ResearchSource(
        "web_search", "https://example.com/a", "Market", 
        "Revenue growth increased 20 percent this year. Customers reported higher demand."
        , 0.9, {"adapter": "test"}
    )
    result = engine.run("market growth", task_id="t1", organization_id=7, sources=[source, source])
    assert result["status"] == "ok"
    assert len(result["sources"]) == 1
    assert len(result["claims"]) == 2
    assert result["evidence_package"]["digest"]
    assert result["governance"]["read_only"] is True
    assert result["governance"]["auto_execute"] is False


def test_research_engine_detects_conflicting_claims():
    engine = ResearchEngine()
    items = [
        ResearchSource("official", "https://official.example/a", "Official", "Revenue increased 20 percent in 2026.", 0.98),
        ResearchSource("unknown", "https://unknown.example/a", "Other", "Revenue decreased 20 percent in 2026.", 0.4),
    ]
    result = engine.run("revenue", task_id="t2", organization_id=7, sources=items, source_ids=["web_search"])
    assert len(result["contradictions"]) == 1
    assert result["contradictions"][0]["status"] == "review_required"


def test_research_engine_fails_closed_without_evidence():
    result = ResearchEngine().run("market research", task_id="t3", organization_id=7, sources=[])
    assert result["status"] == "no_evidence"
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["database_mutation"] is False
