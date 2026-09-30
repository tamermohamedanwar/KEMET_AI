from pathlib import Path


def test_content_approval_status_route_is_read_only_and_fail_closed():
    text = Path("app/routes/command_center.py").read_text()
    assert '@command_center_bp.get("/api/bos/content-approval-status")' in text
    assert 'PENDING_HUMAN_APPROVAL' in text
    assert 'publication_requested' in text
    assert 'external_publication' in text
    assert 'execution_authority' in text
    assert 'truth_boundary' in text
    assert 'content_approval_status_unavailable' in text


def test_content_approval_status_does_not_auto_approve_or_publish():
    text = Path("app/routes/command_center.py").read_text()
    start = text.index('@command_center_bp.get("/api/bos/content-approval-status")')
    end = text.index('@command_center_bp.get("/api/bos/mendes-episode-readiness/<job_id>")', start)
    route = text[start:end]
    assert 'PENDING_HUMAN_APPROVAL' in route
    assert 'publication_requested": False' in route
    assert 'external_publication": False' in route
    assert 'execution_authority": False' in route
    assert '.execute(' not in route


def test_command_center_exposes_content_approval_status_surface():
    text = Path("app/templates/command_center.html").read_text()
    assert '/command-center/api/bos/content-final-approval' in text
    assert 'PENDING HUMAN APPROVAL' in text
    assert 'No publication or approval was executed.' in text
    assert 'Publication Preflight:' in text
