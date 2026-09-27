from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskClassification:
    task_type: str
    capabilities: frozenset[str]
    risk: str = "low"
    confidence: float = 0.5


_RULES = (
    ("coding", ("code", "coding", "debug", "bug", "api", "python", "flask", "website", "app", "bot"), {"coding", "tool_calling"}),
    ("research", ("research", "compare", "comparison", "analyze", "analysis", "report", "market", "study"), {"research", "long_context", "reasoning"}),
    ("reasoning", ("why", "explain", "calculate", "strategy", "decision", "plan", "reasoning"), {"reasoning"}),
    ("multimodal", ("image", "photo", "picture", "video", "audio", "visual"), {"multimodal"}),
    ("automation", ("automate", "automation", "workflow", "execute", "send", "create", "update"), {"agentic", "tool_calling"}),
)


def classify_task(prompt: str) -> TaskClassification:
    text = (prompt or "").strip().lower()
    matched: list[tuple[str, set[str]]] = []
    for task_type, keywords, capabilities in _RULES:
        if any(keyword in text for keyword in keywords):
            matched.append((task_type, set(capabilities)))
    if not matched:
        return TaskClassification("general", frozenset({"reasoning"}), confidence=0.4)
    capabilities: set[str] = set()
    for _, values in matched:
        capabilities.update(values)
    task_type = matched[0][0] if len(matched) == 1 else "multi_task"
    risk = "high" if "automation" in {item[0] for item in matched} else "low"
    confidence = min(0.95, 0.65 + 0.1 * (len(matched) - 1))
    return TaskClassification(task_type, frozenset(capabilities), risk, confidence)


def classification_snapshot(prompt: str) -> dict[str, object]:
    result = classify_task(prompt)
    return {"task_type": result.task_type, "capabilities": sorted(result.capabilities),
            "risk": result.risk, "confidence": result.confidence}
