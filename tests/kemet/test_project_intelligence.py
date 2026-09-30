from app.core.federation.project_intelligence import ProjectIntelligenceService


class FakeGateway:
    def snapshot(self, organization_id, user_id, project_id="kemet-ai", task_id=None, termux=None):
        class Snapshot:
            conversations = ({"provider_id": "openai", "summary": "project context"},)
            termux = {"workspace": "~/products/Kemet_AI"}
        return Snapshot()


def test_project_intelligence_is_tenant_scoped():
    service = ProjectIntelligenceService(FakeGateway())
    result = service.snapshot(7, 11)
    assert result.organization_id == 7
    assert result.user_id == 11
    assert result.project_id == "kemet-ai"
    assert result.continuity["conversation_count"] == 1


def test_project_intelligence_handoff_state_is_bounded():
    state = ProjectIntelligenceService._handoff_state()
    assert "available" in state
    assert len(state.get("latest_checkpoints", [])) <= 12
    assert len(state.get("recovered_gaps", [])) <= 20
