from app.core.federation.routing_preview import FederationRoutingPreviewService


def test_preview_is_read_only_when_no_verified_provider():
    result = FederationRoutingPreviewService().preview(
        "Research the market and compare competitors", organization_id=1, verified_provider_ids=set()
    )
    assert result.task_type == "research"
    assert "research" in result.capabilities
    assert result.provider is None
    assert result.specialist is None
    assert result.execution_allowed is False


def test_preview_requires_approval_for_automation(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "preview-test-key")
    result = FederationRoutingPreviewService().preview(
        "automate sending follow-up messages to leads", organization_id=1,
        verified_provider_ids={"openai"}
    )
    assert result.risk == "high"
    assert result.approval_required is True
    assert result.execution_allowed is True


def test_preview_respects_verified_provider_boundary(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "preview-test-key")
    result = FederationRoutingPreviewService().preview(
        "build a Flask website", organization_id=1, verified_provider_ids={"openai"}
    )
    assert result.provider is not None
    assert result.provider["provider_id"] == "openai"
    assert result.provider["model_id"] == "gpt-5.6"
    assert result.specialist is None


def test_preview_never_selects_unverified_specialist():
    result = FederationRoutingPreviewService().preview(
        "research and compare automation platforms", organization_id=1,
        verified_provider_ids={"openai"}
    )
    assert result.specialist is None
