def test_decision_feedback_loop_aggregates_signals():
    from app.services.decision_feedback_loop import decision_feedback_loop
    result = decision_feedback_loop.build([
        {"decision_id": "a", "signal": "positive"},
        {"decision_id": "b", "signal": "negative"},
        {"decision_id": "c", "signal": "positive"},
    ])
    assert result["success"] is True
    assert result["signals"] == {"positive": 2, "neutral": 0, "negative": 1}
    assert result["learning_signal"] > 0


def test_decision_feedback_loop_fails_closed_on_invalid_signal():
    from app.services.decision_feedback_loop import decision_feedback_loop
    result = decision_feedback_loop.build([{"signal": "execute_now"}])
    assert result["feedback_count"] == 0
    assert result["learning_signal"] == 0.0


def test_decision_feedback_loop_is_non_executing():
    from app.services.decision_feedback_loop import decision_feedback_loop
    result = decision_feedback_loop.build([])
    assert result["governance"]["auto_execute"] is False
    assert result["governance"]["database_mutation"] is False
    assert result["governance"]["human_approval_required"] is True
