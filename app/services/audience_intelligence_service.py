from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


class AudienceIntelligenceService:
    VERSION = "1.0"
    SCHEMA = "kemet.audience_intelligence.v1"
    SIGNALS = ("topic_demand", "hook_strength", "retention", "shareability", "conversion_intent")

    def build_hypothesis(self, *, organization_id: int, audience: str, topic: str,
                         platform: str = "youtube", language: str = "ar-EG",
                         observed_signals: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        audience = self._text(audience, "audience_required", 500)
        topic = self._text(topic, "topic_required", 240)
        platform = self._text(platform, "platform_required", 40).lower()
        signals = self._normalize_signals(observed_signals or {})
        payload = {
            "schema": self.SCHEMA, "version": self.VERSION,
            "organization_id": int(organization_id), "audience": audience,
            "topic": topic, "platform": platform, "language": language,
            "signals": signals, "evidence_status": "unmeasured" if not observed_signals else "observed_input",
            "hypotheses": {
                "audience": f"{audience} may respond to {topic}",
                "hook": "a concrete unresolved question in the opening seconds",
                "retention": "short escalating beats with a clear payoff",
                "conversion": "continue the story through a governed owned-audience channel",
            },
            "rule": "hypothesis_is_not_observed_demand",
            "governance": self._governance(),
        }
        payload["hypothesis_digest"] = self._digest(payload)
        return payload

    def score_content_experiment(self, *, hypothesis: Mapping[str, Any],
                                 observations: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(hypothesis, Mapping) or not hypothesis.get("hypothesis_digest"):
            raise ValueError("hypothesis_required")
        if not isinstance(observations, Mapping):
            raise ValueError("observations_required")
        metrics = {}
        for key in self.SIGNALS:
            value = observations.get(key)
            if value is None:
                metrics[key] = None
                continue
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid_signal:{key}") from exc
            if number < 0 or number > 100:
                raise ValueError(f"signal_out_of_range:{key}")
            metrics[key] = round(number, 4)
        measured = [v for v in metrics.values() if v is not None]
        return {
            "schema": "kemet.audience_intelligence_observation.v1",
            "status": "observed" if measured else "unmeasured",
            "hypothesis_digest": str(hypothesis["hypothesis_digest"]),
            "signals": metrics,
            "learning": self._learning(metrics),
            "causal_claim": False,
            "governance": self._governance(),
        }

    @staticmethod
    def _learning(metrics: Mapping[str, Any]) -> list[str]:
        actions = []
        if metrics.get("hook_strength") is not None and metrics["hook_strength"] < 40:
            actions.append("test_stronger_opening")
        if metrics.get("retention") is not None and metrics["retention"] < 40:
            actions.append("tighten_pacing")
        if metrics.get("shareability") is not None and metrics["shareability"] < 30:
            actions.append("increase_shareable_emotional_payoff")
        if metrics.get("conversion_intent") is not None and metrics["conversion_intent"] < 30:
            actions.append("clarify_owned_audience_cta")
        return actions or ["collect_more_observations"]

    @staticmethod
    def _normalize_signals(values: Mapping[str, Any]) -> dict[str, Any]:
        result = {}
        for key in AudienceIntelligenceService.SIGNALS:
            value = values.get(key)
            if value is None:
                result[key] = None
                continue
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid_signal:{key}") from exc
            if number < 0 or number > 100:
                raise ValueError(f"signal_out_of_range:{key}")
            result[key] = round(number, 4)
        return result

    @staticmethod
    def _text(value: Any, error: str, limit: int) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(error)
        return text[:limit]

    @staticmethod
    def _org(value: Any) -> None:
        if int(value or 0) <= 0:
            raise ValueError("organization_required")
    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "mode": "advisory", "read_only": True, "execution_authority": False,
            "external_execution": False, "auto_publish": False,
            "human_approval_required": True,
            "canonical_executor": "kemet_canonical_runtime",
        }


audience_intelligence_service = AudienceIntelligenceService()
