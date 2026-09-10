from app.core.intelligence import IntelligenceService


def test_intelligence_ranks_priority():
    signals = [
        {
            "key": "low",
            "title": "Low",
            "priority": "low",
            "confidence": 0.9,
        },
        {
            "key": "high",
            "title": "High",
            "priority": "high",
            "confidence": 0.8,
        },
    ]

    result = IntelligenceService.rank_signals(signals)

    assert result[0]["key"] == "high"
    assert result[1]["key"] == "low"


def test_intelligence_summary():
    result = IntelligenceService.summarize(
        [
            {
                "key": "sales",
                "title": "Sales Opportunity",
                "priority": "high",
                "category": "revenue",
                "message": "High-value lead requires attention.",
                "action": "Contact immediately",
                "confidence": 0.91,
            }
        ]
    )

    assert result["success"] is True
    assert result["signal_count"] == 1
    assert result["priority_counts"]["high"] == 1
    assert result["top_signal"]["key"] == "sales"


def test_intelligence_snapshot():
    result = IntelligenceService.build_snapshot(
        organization_id=1,
        signals=[],
        context={"industry": "general"},
    )

    assert result["success"] is True
    assert result["organization_id"] == 1
    assert result["engine"] == "kemet_intelligence"
    assert result["mode"] == "advisory"
