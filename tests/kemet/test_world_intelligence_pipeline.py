from app.services.world_intelligence_pipeline import world_intelligence_pipeline


def test_pipeline_deduplicates_and_preserves_governance():
    items = [
        {"title": "Signal", "source": "Official", "url": "https://example.com/a", "category": "ai", "confidence": 0.95},
        {"title": "Signal", "source": "Official", "url": "https://example.com/a", "category": "ai", "confidence": 0.95},
        {"title": "Market", "source": "Market source", "url": "https://example.com/m", "category": "markets", "confidence": 0.9},
    ]
    result = world_intelligence_pipeline.process(items)
    assert result["input_count"] == 3
    assert result["unique_count"] == 2
    assert len(result["items"]) == 2
    assert len({item["fingerprint"] for item in result["items"]}) == 2
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False


def test_pipeline_accepts_generators():
    def source():
        yield {"title": "A", "source": "S", "url": "https://example.com/a", "category": "ai", "confidence": 0.8}
        yield {"title": "B", "source": "S", "url": "https://example.com/b", "category": "business", "confidence": 0.7}
    result = world_intelligence_pipeline.process(source())
    assert result["input_count"] == 2
    assert result["unique_count"] == 2


def test_pipeline_preserves_source_trust_and_reports_conflicts():
    items = [
        {"title": "Same Event", "source": "official", "url": "https://official.example/a", "category": "business", "confidence": 0.95},
        {"title": "Same Event", "source": "unknown", "url": "https://unknown.example/a", "category": "business", "confidence": 0.8},
    ]
    result = world_intelligence_pipeline.process(items)
    trusts = sorted(item["source_trust"] for item in result["items"])
    assert trusts == [0.4, 0.98]
    assert all("source_tier" in item for item in result["items"])
    assert all("source_key" in item for item in result["items"])
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["status"] == "review_required"
    assert result["conflicts"][0]["trust_spread"] == 0.58
