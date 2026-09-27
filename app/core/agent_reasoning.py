from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from app.services.ai_service import ask_ai


@dataclass(frozen=True)
class AgentDecision:
    objective: str
    specialist: str
    capabilities: tuple[str, ...]
    tool: str
    rationale: str
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "specialist": self.specialist,
            "capabilities": list(self.capabilities),
            "tool": self.tool,
            "rationale": self.rationale,
            "confidence": self.confidence,
        }


class KemetModelReasoner:
    VERSION = "1.0"

    SYSTEM = """You are Kemet Commander reasoning layer.
Return JSON only.
Choose exactly one specialist and one advisory tool from the supplied catalog.
Never claim execution. Never invent evidence. Never approve external side effects.
The Commander remains the sole orchestrator and Canonical Runtime remains the only executor.
"""

    def __init__(self, model_call: Callable[..., str] | None = None):
        self.model_call = model_call or ask_ai

    def decide(
        self,
        instruction: str,
        *,
        context: dict[str, Any],
        specialists: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        organization_id: int,
    ) -> AgentDecision:
        prompt = self._prompt(instruction, context, specialists, tools)
        raw = self.model_call(prompt, context=json.dumps(context, sort_keys=True, default=str),
                              organization_id=organization_id)
        parsed = self._parse(raw)
        return self._validate(parsed, specialists, tools)

    def _prompt(self, instruction: str, context: dict[str, Any],
                specialists: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        return (
            f"{self.SYSTEM}\n"
            f"Instruction: {instruction}\n"
            f"Context: {json.dumps(context, sort_keys=True, default=str)}\n"
            f"Specialists: {json.dumps(specialists, sort_keys=True)}\n"
            f"Tools: {json.dumps(tools, sort_keys=True)}\n"
            'Output schema: {"objective":"string","specialist":"id","capabilities":["..."],'
            '"tool":"id","rationale":"string","confidence":0.0}'
        )

    @staticmethod
    def _parse(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        text = str(raw or "").strip()
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
        except (TypeError, ValueError):
            pass
        raise ValueError("agent_reasoning_invalid_structured_output")

    @staticmethod
    def _validate(value: dict[str, Any], specialists: list[dict[str, Any]],
                   tools: list[dict[str, Any]]) -> AgentDecision:
        specialist_ids = {str(item["id"]) for item in specialists}
        tool_ids = {str(item["id"]) for item in tools}
        specialist = str(value.get("specialist") or "")
        tool = str(value.get("tool") or "")
        if specialist not in specialist_ids:
            raise ValueError("agent_reasoning_unknown_specialist")
        if tool not in tool_ids:
            raise ValueError("agent_reasoning_unknown_tool")
        confidence = float(value.get("confidence", 0.0))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("agent_reasoning_invalid_confidence")
        return AgentDecision(
            objective=str(value.get("objective") or "").strip(),
            specialist=specialist,
            capabilities=tuple(sorted({str(x) for x in value.get("capabilities", []) if str(x)})),
            tool=tool,
            rationale=str(value.get("rationale") or "").strip(),
            confidence=confidence,
        )
