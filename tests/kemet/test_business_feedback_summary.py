def test_feedback_summary_route_exists():
    from app import create_app
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/bos/business-control-loop/feedback-summary" in routes


def test_feedback_summary_service_is_governed():
    from app.services.decision_feedback_loop import decision_feedback_loop
    result = decision_feedback_loop.build([])
    assert result["mode"] == "observational"
    assert result["governance"]["human_approval_required"] is True
    assert result["governance"]["auto_execute"] is False
