from app import create_app
from app.services.final_content_approval_service import final_content_approval_service


def _build():
    app = create_app()
    with app.app_context():
        return final_content_approval_service.build(organization_id=1)


def test_final_approval_route_contract_is_read_only():
    from pathlib import Path
    text = Path("app/routes/command_center.py").read_text()
    assert '@command_center_bp.get("/api/bos/content-final-approval")' in text
    start = text.index('@command_center_bp.get("/api/bos/content-final-approval")')
    end = text.index('@command_center_bp.get("/api/bos/content-approval-status")', start)
    route = text[start:end]
    assert '.execute(' not in route
    assert 'execution_authority' in route
    assert 'content_final_approval_unavailable' in route


def test_final_approval_service_has_read_only_governance():
    result = _build()
    assert result["governance"]["read_only"] is True
    assert result["governance"]["execution_authority"] is False
    assert result["governance"]["external_publication"] is False
    assert result["governance"]["mcp"] is False


def test_final_approval_packet_preserves_lineage_and_human_gate():
    result = _build()
    if result.get("success"):
        packet = result["approval_packet"]
        assert packet["approval"]["status"] == "PENDING_HUMAN_APPROVAL"
        assert packet["approval"]["approver_required"] is True
        assert packet["execution"]["execution_authority"] is False
        assert len(packet["packet_digest"]) == 64
        assert result["publication_preflight"]["execution_authority"] is False
        assert result["publication_preflight"]["external_publication"] is False
        assert result["voice_provider_decision"]["selected"] is False
        assert result["voice_provider_decision"]["governance"]["execution_authority"] is False
    else:
        assert result["governance"]["execution_authority"] is False


def test_final_approval_does_not_mark_publication_ready_without_authority():
    result = _build()
    if result.get("success"):
        preflight = result["publication_preflight"]
        assert preflight["ready"] is False
        assert preflight["status"] == "BLOCKED"
        assert any("publishing" in item or "approval" in item or "voice" in item or "budget" in item for item in preflight["blockers"])
        assert "select_voice_provider" not in preflight["next_actions"]
        assert "capture_verified_cost" in preflight["next_actions"]
        assert "connect_and_verify:youtube" in preflight["next_actions"]
