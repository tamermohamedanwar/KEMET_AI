def test_conflict_detector_flags_trust_spread():
    from app.services.world_intelligence_conflict import world_intelligence_conflict_detector

    items = [
        {"title": "Market outlook", "category": "markets", "source_trust": 0.98, "confidence": 0.9},
        {"title": "Market outlook", "category": "markets", "source_trust": 0.4, "confidence": 0.7},
    ]
    result = world_intelligence_conflict_detector.detect(items)
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["status"] == "review_required"


def test_conflict_detector_is_fail_safe():
    from app.services.world_intelligence_conflict import world_intelligence_conflict_detector

    result = world_intelligence_conflict_detector.detect([])
    assert result["conflicts"] == []
    assert result["governance"]["read_only"] is True
    assert result["governance"]["auto_execute"] is False
