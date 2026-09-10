def test_feedback_summary_route_exists():
    from app import create_app
    app = create_app()
    assert "/api/bos/business-control-loop/feedback-summary" in {r.rule for r in app.url_map.iter_rules()}


def test_feedback_summary_is_org_scoped():
    from app.services.decision_feedback_loop import decision_feedback_loop
    result = decision_feedback_loop.build([{"signal": "positive"}])
    assert result["governance"]["read_only"] is True
    assert result["governance"]["auto_execute"] is False
