from __future__ import annotations

import pytest

from app.core.agent_reasoning import KemetModelReasoner
from app.core.agent_runtime import KemetAgentRuntime
from app.core.agent_tool_registry import kemet_agent_tool_registry


@pytest.fixture(autouse=True)
def app_context():
    from wsgi import application
    with application.app_context():
        yield


def test_reasoner_enforces_structured_specialist_and_tool_selection():
    def fake_model(prompt, **kwargs):
        return '{"objective":"grow revenue","specialist":"revenue","capabilities":["revenue","sales"],"tool":"revenue_intelligence","rationale":"revenue signal","confidence":0.91}'

    decision = KemetModelReasoner(model_call=fake_model).decide(
        "improve sales",
        context={"revenue": {"status": "known"}},
        specialists=[
            {"id": "revenue", "description": "revenue", "capabilities": ["revenue", "sales"]}
        ],
        tools=kemet_agent_tool_registry.manifests(),
        organization_id=1,
    )

    assert decision.specialist == "revenue"
    assert decision.tool == "revenue_intelligence"
    assert decision.confidence == 0.91


def test_reasoner_rejects_unknown_tool():
    def fake_model(prompt, **kwargs):
        return '{"objective":"x","specialist":"revenue","capabilities":[],"tool":"unknown","rationale":"x","confidence":0.8}'

    with pytest.raises(ValueError, match="unknown_tool"):
        KemetModelReasoner(model_call=fake_model).decide(
            "x",
            context={},
            specialists=[{"id": "revenue", "description": "revenue", "capabilities": ["revenue"]}],
            tools=kemet_agent_tool_registry.manifests(),
            organization_id=1,
        )


def test_commander_runtime_exposes_model_reasoning_boundary():
    def fake_model(prompt, **kwargs):
        return '{"objective":"understand business","specialist":"business","capabilities":["business"],"tool":"business_context","rationale":"business context needed","confidence":0.88}'

    runtime = KemetAgentRuntime(reasoner=KemetModelReasoner(model_call=fake_model))
    run = runtime.ask("understand the business situation", organization_id=1)
    _, decision = runtime.reason(run)

    assert decision.specialist == "business"
    assert decision.tool == "business_context"
    assert run.execution is None
    assert runtime.status()["external_execution_authority"] is False
