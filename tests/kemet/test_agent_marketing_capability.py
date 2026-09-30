from app import create_app
from app.core.agent_tool_registry import kemet_agent_tool_registry
from app.core.task_classifier import classify_task
from app.core.agent_runtime import KemetAgentRuntime
from app.services.business_control_loop import business_control_loop


def test_marketing_tool_is_canonical_agent_capability():
    tool = kemet_agent_tool_registry.get("marketing_intelligence")

    assert tool is not None
    assert "marketing" in tool.capabilities
    assert "research" in tool.capabilities
    assert "audience" in tool.capabilities
    assert "optimization" in tool.capabilities
    assert tool.requires_approval is False


def test_marketing_requests_are_classified_with_marketing_capability():
    result = classify_task(
        "Create a marketing campaign for our product and identify the target audience."
    )

    assert "marketing" in result.capabilities
    assert "audience" in result.capabilities
    assert "research" in result.capabilities


def test_agent_runtime_exposes_marketing_specialist():
    specialists = KemetAgentRuntime._specialists()

    marketing = next(item for item in specialists if item["id"] == "marketing")

    assert "marketing" in marketing["capabilities"]
    assert "audience" in marketing["capabilities"]
    assert "optimization" in marketing["capabilities"]


def test_business_control_loop_exposes_governed_marketing_pipeline():
    app = create_app()

    with app.app_context():
        result = business_control_loop.build(7, [])

    assert result["success"] is True

    marketing = result["marketing_intelligence"]

    assert marketing["enabled"] is True
    assert marketing["external_execution"] is False
    assert marketing["automatic_action"] is False
    assert marketing["requires_human_approval"] is True

    assert marketing["pipeline"] == [
        "research",
        "audience_intelligence",
        "content_strategy",
        "experiment",
        "campaign_governance",
        "human_approval",
        "outcome_measurement",
        "learning",
        "next_action",
    ]
