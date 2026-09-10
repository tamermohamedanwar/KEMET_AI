def test_business_feedback_fails_closed_without_organization():
    from app.services.business_feedback import business_feedback
    result = business_feedback.build(None)
    assert result["success"] is False
    assert result["error"] == "organization_required"


def test_business_feedback_accepts_observational_signal():
    from app.services.business_feedback import business_feedback
    result = business_feedback.build(7, decision_id="decision-1", capability_id="kemet.sales_follow_up", signal="positive", note="Observed improvement")
    assert result["success"] is True
    assert result["feedback"]["signal"] == "positive"
    assert result["governance"]["auto_execute"] is False


def test_business_feedback_rejects_unknown_signal():
    from app.services.business_feedback import business_feedback
    result = business_feedback.build(7, signal="execute_now")
    assert result["success"] is False
    assert result["error"] == "invalid_feedback_signal"


def test_business_feedback_bounds_note_size():
    from app.services.business_feedback import business_feedback
    result = business_feedback.build(7, note="x" * 1000)
    assert result["success"] is True
    assert len(result["feedback"]["note"]) == 500


def test_business_feedback_route_exists():
    from app import create_app
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/bos/business-control-loop/feedback" in routes
