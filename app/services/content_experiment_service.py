from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.services.audience_intelligence_service import audience_intelligence_service


class ContentExperimentService:
    VERSION = "1.0"
    SCHEMA = "kemet.content_experiment.v1"
    STATES = ("DRAFT", "READY_FOR_REVIEW", "APPROVED", "PUBLISHED", "OBSERVED", "CLOSED")

    def build(self, *, organization_id: int, content_id: str, title: str,
              audience: str, hook: str, story: str, cta: str,
              platforms: list[str] | tuple[str, ...] = ("youtube", "tiktok", "instagram", "facebook"),
              telegram_cta: str = "Continue the story on Telegram") -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        values = {"content_id": content_id, "title": title, "audience": audience,
                  "hook": hook, "story": story, "cta": cta}
        for key, value in values.items():
            if not str(value or "").strip():
                raise ValueError(f"{key}_required")
        selected = self._platforms(platforms)
        hypothesis = audience_intelligence_service.build_hypothesis(
            organization_id=int(organization_id), audience=str(audience),
            topic=str(title), platform=selected[0],
        )
        payload = {
            "schema": self.SCHEMA, "version": self.VERSION,
            "experiment_id": "ce_" + hashlib.sha256(
                json.dumps({"organization_id": int(organization_id), "content_id": str(content_id)},
                           sort_keys=True).encode()
            ).hexdigest()[:32],
            "organization_id": int(organization_id), "content_id": str(content_id),
            "title": str(title)[:200], "audience": str(audience)[:500],
            "hypothesis": hypothesis,
            "creative": {"hook": str(hook)[:1000], "story": str(story)[:8000],
                         "cta": str(cta)[:500], "telegram_cta": str(telegram_cta)[:500]},
            "platforms": list(selected),
            "primary_metrics": ["retention_rate", "shares", "qualified_views", "telegram_join_intent", "revenue"],
            "monetization_hypothesis": "owned_audience_conversion_can_compound_platform_reach",
            "state": "READY_FOR_REVIEW",
            "approval": {"required": True, "status": "PENDING"},
            "execution": {"external": False, "auto_publish": False,
                          "canonical_executor": "kemet_canonical_runtime"},
            "governance": {"read_only": True, "human_approval_required": True},
        }
        payload["experiment_digest"] = self._digest(payload)
        return payload

    def observe(self, *, experiment: Mapping[str, Any],
                observations: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(experiment, Mapping) or not experiment.get("experiment_digest"):
            raise ValueError("experiment_required")
        if not isinstance(observations, Mapping):
            raise ValueError("observations_required")
        required = ("retention_rate", "shares", "qualified_views", "telegram_join_intent", "revenue")
        normalized = {}
        for key in required:
            value = observations.get(key, 0)
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid_metric:{key}") from exc
            if number < 0:
                raise ValueError(f"negative_metric:{key}")
            normalized[key] = round(number, 4)
        return {
            "schema": "kemet.content_experiment_observation.v1",
            "status": "OBSERVED", "experiment_digest": str(experiment["experiment_digest"]),
            "metrics": normalized, "learning": self._learning(normalized),
            "causal_claim": False, "revenue_authoritative": True,
            "governance": {"read_only": True, "execution_authority": False,
                           "auto_policy_change": False, "human_review_required": True},
        }

    @staticmethod
    def _learning(metrics: Mapping[str, float]) -> list[str]:
        actions = []
        if metrics["retention_rate"] < 35:
            actions.append("strengthen_hook")
        if metrics["telegram_join_intent"] < 1:
            actions.append("improve_owned_audience_cta")
        if metrics["qualified_views"] > 0 and metrics["revenue"] > 0:
            actions.append("compare_revenue_per_qualified_view")
        return actions or ["preserve_pattern_and_collect_more_data"]

    @staticmethod
    def _platforms(platforms: Any) -> tuple[str, ...]:
        if isinstance(platforms, str):
            platforms = [platforms]
        if not isinstance(platforms, (list, tuple, set)):
            raise ValueError("platforms_required")
        allowed = {"youtube", "tiktok", "instagram", "facebook", "telegram"}
        result = tuple(dict.fromkeys(str(x).strip().lower() for x in platforms if str(x).strip()))
        if not result or any(x not in allowed for x in result):
            raise ValueError("unsupported_platform")
        return result

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode()).hexdigest()


content_experiment_service = ContentExperimentService()
