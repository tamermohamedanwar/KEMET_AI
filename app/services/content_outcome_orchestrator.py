from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.services.creator_commerce_service import creator_commerce_service
from app.services.mendes.hikayat_mendes_story_engine import hikayat_mendes_story_engine
from app.services.media_production_pipeline import media_production_pipeline
from app.services.social_distribution_contract import SocialDistributionContract
from app.services.next_episode_learning_service import next_episode_learning_service
from app.services.content_revenue_attribution_service import content_revenue_attribution_service


class ContentOutcomeOrchestrator:
    VERSION = "1.0"
    METRICS = ("impressions", "views", "watch_time_seconds", "retention_rate", "shares", "comments",
               "followers_gained", "clicks", "qualified_views", "conversions", "revenue")
    PLATFORMS = ("youtube", "tiktok", "instagram", "facebook", "telegram", "whatsapp")

    def build_plan(self, *, organization_id: int, episode: Mapping[str, Any],
                   platforms: list[str] | tuple[str, ...] = ("youtube", "tiktok", "instagram", "facebook"),
                   duration_seconds: int = 90, language: str = "ar-EG") -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not isinstance(episode, Mapping) or not episode.get("title"):
            raise ValueError("episode_required")
        selected = self._platforms(platforms)
        story = dict(episode)
        media = media_production_pipeline.build_plan(
            organization_id=organization_id, episode=story, language=language, duration_seconds=duration_seconds
        )
        distribution = [
            SocialDistributionContract.plan(platform, asset_uri="pending:approved_media_asset",
                                            title=str(story["title"])[:200], caption=str(story.get("caption") or story["title"])[:1000])
            for platform in selected
        ]
        opportunity = creator_commerce_service.build_opportunity(
            topic=str(story["title"]), audience="Egyptian and Arabic-speaking story audience",
            demand_score=0, competition_score=0, monetization_score=0,
            recommended_format="story", commercial_intent="informational", platforms=selected[:4],
        )
        content_id = self._fingerprint({"organization_id": int(organization_id), "episode": story, "platforms": selected})
        return {
            "success": True, "engine": "kemet_content_outcome_orchestrator", "version": self.VERSION,
            "status": "proposal", "organization_id": int(organization_id), "content_id": content_id,
            "flow": ["story", "production", "quality_gate", "approval", "distribution", "measurement", "learning"],
            "story": {"episode_id": story.get("episode_id"), "title": story.get("title"),
                      "historical_label_required": story.get("historical_label_required", True)},
            "production": media,
            "distribution": distribution,
            "commerce": {"opportunity": opportunity["opportunity"], "monetization": opportunity["recommendation"],
                          "rule": "optimize_for_revenue_per_qualified_view_not_raw_views"},
            "measurement": {"metrics": list(self.METRICS), "primary": ["retention_rate", "shares", "qualified_views", "revenue"],
                            "attribution_required": True, "causal_claim": False},
            "learning": {"mode": "observational", "feeds_next_episode": True, "auto_policy_change": False,
                         "auto_publish": False, "recommendation_only": True},
            "governance": self._governance(),
        }

    def evaluate_results(self, *, planned: Mapping[str, Any], results: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(planned, Mapping) or not planned.get("content_id"):
            raise ValueError("plan_required")
        if not isinstance(results, Mapping):
            raise ValueError("results_required")
        metrics = self._metrics(results.get("metrics") or results)
        retention = metrics.get("retention_rate", 0.0)
        shares = metrics.get("shares", 0.0)
        qualified = metrics.get("qualified_views", 0.0)
        revenue = metrics.get("revenue", 0.0)
        views = metrics.get("views", 0.0)
        revenue_per_1000 = round((revenue / qualified) * 1000, 4) if qualified > 0 else None
        revenue_attribution = content_revenue_attribution_service.evaluate(
            content_id=str(planned["content_id"]),
            metrics=metrics,
            payment_evidence=results.get("payment_evidence") or [],
            organization_id=int(planned.get("organization_id") or 0),
            publication_id=str(results.get("publication_id") or planned.get("publication_id") or ""),
            execution_key=str(results.get("execution_key") or planned.get("execution_key") or ""),
        )
        return {
            "success": True, "engine": self.__class__.__name__, "version": self.VERSION,
            "status": "observed", "content_id": str(planned["content_id"]), "metrics": metrics,
            "signals": {"retention": self._band(retention, (35, 55)), "sharing": self._band_ratio(shares, views),
                         "qualified_view_depth": self._band_ratio(qualified, views), "revenue": self._band(revenue, (1, 10))},
            "economics": {
                "revenue_per_1000_qualified_views": revenue_per_1000,
                "verified_content_revenue": revenue_attribution["revenue"],
                "verified_content_economics": revenue_attribution["economics"],
            },
            "revenue_attribution": revenue_attribution["attribution"],
            "learning": self._learning(metrics),
            "next_episode": next_episode_learning_service.build_recommendation(
                organization_id=int(planned.get("organization_id") or 0),
                episode=planned.get("story") or {},
                observed={"metrics": metrics},
            ),
            "causal_claim": False, "governance": self._governance(),
        }

    def _learning(self, metrics: Mapping[str, float]) -> list[dict[str, str]]:
        actions = []
        retention = metrics.get("retention_rate", 0.0)
        views = metrics.get("views", 0.0)
        shares = metrics.get("shares", 0.0)
        if retention < 35:
            actions.append({"signal": "low_retention", "next_action": "strengthen_hook_and_pacing"})
        elif retention >= 55:
            actions.append({"signal": "strong_retention", "next_action": "preserve_opening_pattern"})
        if views and shares / views < 0.01:
            actions.append({"signal": "low_sharing", "next_action": "improve_emotional_payoff_and_shareability"})
        if metrics.get("revenue", 0.0) > 0 and metrics.get("qualified_views", 0.0) > 0:
            actions.append({"signal": "monetization_observed", "next_action": "compare_revenue_per_qualified_view"})
        return actions or [{"signal": "insufficient_signal", "next_action": "collect_more_observations"}]

    @classmethod
    def _metrics(cls, payload: Mapping[str, Any]) -> dict[str, float]:
        normalized = {}
        for name in cls.METRICS:
            value = payload.get(name, 0)
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid_metric:{name}") from exc
            if number < 0:
                raise ValueError(f"negative_metric:{name}")
            normalized[name] = round(number, 4)
        if normalized["retention_rate"] > 100:
            raise ValueError("retention_rate_out_of_range")
        return normalized

    @classmethod
    def _platforms(cls, platforms: Any) -> tuple[str, ...]:
        if isinstance(platforms, str):
            platforms = [platforms]
        if not isinstance(platforms, (list, tuple, set)):
            raise ValueError("platforms_required")
        result = tuple(dict.fromkeys(str(item).strip().lower() for item in platforms if str(item).strip()))
        if not result or any(item not in cls.PLATFORMS for item in result):
            raise ValueError("unsupported_platform")
        return result

    @staticmethod
    def _band(value: float, thresholds: tuple[float, float]) -> str:
        if value < thresholds[0]:
            return "low"
        if value >= thresholds[1]:
            return "strong"
        return "medium"

    @staticmethod
    def _band_ratio(numerator: float, denominator: float) -> str:
        if denominator <= 0:
            return "unknown"
        ratio = numerator / denominator
        if ratio < 0.01:
            return "low"
        if ratio >= 0.05:
            return "strong"
        return "medium"

    @staticmethod
    def _fingerprint(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"mode": "advisory", "read_only": True, "execution_authority": False,
                "external_execution": False, "database_mutation": False, "auto_publish": False,
                "human_approval_required": True, "canonical_executor": "kemet_canonical_runtime"}


content_outcome_orchestrator = ContentOutcomeOrchestrator()
