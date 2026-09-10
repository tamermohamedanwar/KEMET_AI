def test_world_intelligence_normalizes_and_ranks():
    from app.services.world_intelligence_service import world_intelligence
    result = world_intelligence.brief([
        {"title": "Low", "source": "A", "url": "https://a", "category": "ai", "confidence": 0.4},
        {"title": "High", "source": "B", "url": "https://b", "category": "business", "confidence": 0.9},
        {"title": "Invalid", "source": "", "url": "https://c", "confidence": 1.0},
    ])
    assert [x["title"] for x in result["items"]] == ["High", "Low"]

def test_world_intelligence_fail_safe_contract():
    from app.services.world_intelligence_service import world_intelligence
    result = world_intelligence.brief([])
    assert result["items"] == []
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["database_mutation"] is False


def test_world_intelligence_verifies_and_recommends():
    from app.services.world_intelligence_service import world_intelligence
    result = world_intelligence.brief([
        {"title": "AI signal", "source": "Official", "url": "https://example.com/a", "category": "ai", "confidence": 0.95},
        {"title": "Weak signal", "source": "Unknown", "url": "bad", "category": "general", "confidence": 0.2},
    ])
    assert result["items"][0]["verified"] is True
    assert result["items"][0]["recommendation"] == "INTEGRATE"
    assert result["items"][1]["recommendation"] == "WATCH"
