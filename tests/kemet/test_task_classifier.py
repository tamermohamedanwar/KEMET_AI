from app.core.task_classifier import classify_task, classification_snapshot


def test_coding_task_adds_coding_capability():
    result = classify_task("build a Python bot")
    assert result.task_type == "coding"
    assert "coding" in result.capabilities
    assert "tool_calling" in result.capabilities


def test_research_comparison_requires_research():
    result = classify_task("compare two products and analyze the market")
    assert result.task_type == "research"
    assert {"research", "reasoning"}.issubset(result.capabilities)


def test_multimodal_task_requires_multimodal():
    result = classify_task("analyze this image")
    assert "multimodal" in result.capabilities


def test_automation_is_high_risk_classification():
    result = classify_task("automate and send the report")
    assert result.risk == "high"
    assert "agentic" in result.capabilities


def test_unknown_task_is_deterministic_and_safe():
    first = classification_snapshot("hello")
    second = classification_snapshot("hello")
    assert first == second
    assert first["task_type"] == "general"
