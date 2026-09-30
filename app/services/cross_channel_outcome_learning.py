from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.commercial_outcome_trace import commercial_outcome_trace
from app.services.workforce_outcome_learning import workforce_outcome_learning


class CrossChannelOutcomeLearningService:
    VERSION = "1.0"
    SCHEMA = "kemet.cross_channel_outcome_learning.v1"
    CHANNELS = ("web", "telegram", "whatsapp")

    GOVERNANCE = {
        "tenant_scoped": True,
        "read_only": True,
        "observational": True,
        "causal_claim": False,
        "roi_claim": False,
        "execution_authority": False,
        "external_execution": False,
        "auto_execute": False,
        "human_approval_required": True,
        "canonical_runtime_only": True,
        "fail_closed": True,
        "mcp": False,
    }

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def build(
        self,
        organization_id: int,
        *,
        execution_keys: list[str] | None = None,
        period: str = "30d",
    ) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            return {"success": False, "status": "BLOCKED", "error": "organization_required", "governance": dict(self.GOVERNANCE)}

        traces = []
        channels = {channel: {"observed": 0, "revenue_evidence": 0, "outcomes": 0} for channel in self.CHANNELS}
        for key in execution_keys or []:
            trace = commercial_outcome_trace.get(org, str(key))
            if not trace:
                continue
            business = trace.get("business") or {}
            measurement = trace.get("measurement") or {}
            payment = business.get("payment") or {}
            delivery = business.get("delivery") or {}
            channel = ((trace.get("trace") or {}).get("channel") or business.get("channel") or "unknown").lower()
            if channel not in channels:
                channels[channel] = {"observed": 0, "revenue_evidence": 0, "outcomes": 0}
            channels[channel]["observed"] += 1
            channels[channel]["revenue_evidence"] += int(bool((business.get("revenue") or {}).get("evidence_backed")))
            channels[channel]["outcomes"] += int(bool(business.get("outcome")))
            traces.append({
                "execution_key": str(key),
                "channel": channel,
                "outcome": business.get("outcome"),
                "payment_observed": bool(payment.get("evidence_backed")),
                "delivery_observed": bool(delivery.get("evidence_backed")),
                "revenue": business.get("revenue"),
                "roi": business.get("roi"),
                "causal_claim": measurement.get("causal_claim", False),
            })

        snapshot = workforce_outcome_learning.learning_snapshot(org, period=period)
        payload = {
            "success": True,
            "status": "LEARNING_READY",
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": org,
            "period": period,
            "channels": channels,
            "traces": traces,
            "workforce_learning": {
                "status": snapshot.get("status"),
                "snapshot_digest": snapshot.get("snapshot_digest"),
                "decision_learning": snapshot.get("decision_learning", {}),
            },
            "learning": {
                "mode": "observational",
                "cross_channel_comparison": "descriptive_only",
                "ranking_adjustment": "recommendation_only",
                "next_action": "collect_more_real_outcomes" if not traces else "review_observed_outcomes",
            },
            "governance": dict(self.GOVERNANCE),
        }
        payload["learning_digest"] = self._digest(payload)
        return payload


cross_channel_outcome_learning = CrossChannelOutcomeLearningService()
