from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


class NextEpisodeLearningService:
    VERSION = "1.0"

    def build_recommendation(self, *, organization_id: int, episode: Mapping[str, Any],
                             observed: Mapping[str, Any]) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not isinstance(episode, Mapping) or not episode.get("title"):
            raise ValueError("episode_required")
        if not isinstance(observed, Mapping):
            raise ValueError("observations_required")

        metrics = dict(observed.get("metrics") or observed)
        signals = self._signals(metrics)
        recommendations = []
        if signals["retention"] == "low":
            recommendations.append("strengthen_first_3_seconds")
        elif signals["retention"] == "strong":
            recommendations.append("preserve_opening_pattern")
        if signals["sharing"] == "low":
            recommendations.append("increase_emotional_payoff")
        if signals["qualified_views"] == "low":
            recommendations.append("improve_topic_match_and_watch_depth")
        if signals["revenue"] == "strong":
            recommendations.append("retain_monetization_pattern")
        if not recommendations:
            recommendations.append("collect_more_observations")

        next_title = self._next_title(str(episode["title"]), recommendations)
        fingerprint = hashlib.sha256(json.dumps({
            "organization_id": int(organization_id),
            "source_episode": episode.get("episode_id") or episode.get("title"),
            "signals": signals,
            "recommendations": recommendations,
        }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return {
            "success": True,
            "status": "recommendation",
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "source_episode": episode.get("episode_id") or episode.get("title"),
            "next_episode": {"title": next_title, "format": "short_story", "language": "ar-EG"},
            "signals": signals,
            "recommendations": recommendations,
            "learning_digest": fingerprint,
            "execution_authority": False,
            "auto_publish": False,
            "human_approval_required": True,
            "canonical_executor": "kemet_canonical_runtime",
        }

    @staticmethod
    def _signals(metrics: Mapping[str, Any]) -> dict[str, str]:
        def number(name: str) -> float:
            try:
                value = float(metrics.get(name, 0) or 0)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid_metric:{name}") from exc
            if value < 0:
                raise ValueError(f"negative_metric:{name}")
            return value

        retention = number("retention_rate")
        views = number("views")
        shares = number("shares")
        qualified = number("qualified_views")
        revenue = number("revenue")
        return {
            "retention": "low" if retention < 35 else "strong" if retention >= 55 else "medium",
            "sharing": "low" if views <= 0 or shares / views < 0.01 else "strong" if shares / views >= 0.05 else "medium",
            "qualified_views": "low" if views <= 0 or qualified / views < 0.25 else "strong" if qualified / views >= 0.60 else "medium",
            "revenue": "strong" if revenue > 0 else "unknown",
        }

    @staticmethod
    def _next_title(title: str, recommendations: list[str]) -> str:
        suffix = " — الحلقة التالية"
        if "strengthen_first_3_seconds" in recommendations:
            suffix = " — بداية أقوى"
        elif "increase_emotional_payoff" in recommendations:
            suffix = " — نهاية أكثر تأثيرًا"
        return f"{title}{suffix}"[:200]


next_episode_learning_service = NextEpisodeLearningService()
