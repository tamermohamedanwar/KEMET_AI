from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


class ExecutiveBriefError(ValueError):
    pass


class ExecutiveBriefService:
    VERSION = "1.0"
    MAX_ITEMS = 6

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _text(value: Any, fallback: str = "") -> str:
        return " ".join(str(value or fallback).split()).strip()

    def build(self, *, task_id: str, organization_id: int, question: str, research: dict[str, Any]) -> dict[str, Any]:
        if not task_id or not organization_id or not self._text(question):
            raise ExecutiveBriefError("brief_identity_required")
        synthesis = research.get("synthesis") or {}
        claims = list(research.get("claims") or [])
        sources = list(research.get("sources") or [])
        contradictions = list(research.get("contradictions") or [])
        corroborated = list(research.get("corroboration") or [])
        confidence = float(synthesis.get("confidence", 0.0) or 0.0)
        evidence_status = self._text(synthesis.get("status"), "insufficient_evidence")
        findings = [{
            "claim_id": c.get("claim_id"), "finding": self._text(c.get("text")),
            "source_id": c.get("source_id"), "locator": c.get("locator"),
            "confidence": round(float(c.get("confidence", 0.0) or 0.0), 4),
        } for c in claims[: self.MAX_ITEMS] if self._text(c.get("text"))]
        opportunities = []
        risks = []
        for item in findings:
            text = item["finding"].lower()
            if any(x in text for x in ("growth", "increase", "demand", "opportunity", "improve", "gain")):
                opportunities.append(item["finding"])
            if any(x in text for x in ("risk", "decline", "decrease", "loss", "negative", "complaint")):
                risks.append(item["finding"])
        if not opportunities and corroborated:
            opportunities = ["Corroborated signals merit focused business review before action."]
        if not risks and contradictions:
            risks = ["Conflicting evidence requires validation before treating the signal as a decision fact."]
        review_required = bool(contradictions) or not sources or evidence_status in {"insufficient_evidence", "review_required"}
        recommendation = (
            "Validate the strongest evidence and approve a bounded next step." if review_required
            else "Use the supported findings to define a bounded next step, then measure the outcome."
        )
        brief = {
            "version": self.VERSION, "type": "executive_decision_brief",
            "task_id": task_id, "organization_id": int(organization_id),
            "question": self._text(question),
            "executive_summary": (
                f"Evidence status: {evidence_status}. {len(findings)} findings from {len(sources)} sources; "
                f"confidence {round(confidence * 100)}%."
            ),
            "findings": findings,
            "why_it_matters": (
                "The evidence can inform a business decision, but its strength depends on source quality, corroboration, and unresolved conflicts."
            ),
            "confidence": round(confidence, 4),
            "conflicts": contradictions[: self.MAX_ITEMS],
            "opportunities": opportunities[: self.MAX_ITEMS],
            "risks": risks[: self.MAX_ITEMS],
            "recommended_next_steps": [recommendation, "Record the approved decision and expected outcome.", "Measure the outcome and feed the result back into the decision loop."],
            "decision": {
                "status": "review_required" if review_required else "ready_for_business_review",
                "recommendation": recommendation,
                "human_review_required": True,
                "auto_execute": False,
            },
            "traceability": {
                "source_ids": sorted({str(x.get("source_id")) for x in findings if x.get("source_id")}),
                "claim_ids": [x.get("claim_id") for x in findings if x.get("claim_id")],
                "research_evidence_digest": (research.get("evidence_package") or {}).get("digest"),
            },
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False, "citation_required": True},
        }
        return {**brief, "digest": self._digest(brief)}


executive_brief = ExecutiveBriefService()
