def test_review_queue_surface_is_present():
    from pathlib import Path
    text = Path('app/templates/admin/command_center.html').read_text()
    assert 'decisionReviewQueuePanel' in text
    assert 'Decision Review Queue' in text
    assert 'openApprovalPreview' in text


def test_review_queue_route_is_available():
    from app import create_app
    app = create_app()
    assert '/api/bos/business-control-loop' in {r.rule for r in app.url_map.iter_rules()}
