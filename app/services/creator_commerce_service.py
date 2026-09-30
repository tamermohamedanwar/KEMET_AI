from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping

from app.services.ecommerce_creative_service import ecommerce_creative_service
from app.services.social_distribution_contract import SocialDistributionContract


@dataclass(frozen=True)
class CommerceOpportunity:
    topic: str
    audience: str
    commercial_intent: str
    demand_score: float
    competition_score: float
    monetization_score: float
    recommended_format: str
    platforms: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "audience": self.audience,
            "commercial_intent": self.commercial_intent,
            "demand_score": self.demand_score,
            "competition_score": self.competition_score,
            "monetization_score": self.monetization_score,
            "recommended_format": self.recommended_format,
            "platforms": list(self.platforms),
        }


class CreatorCommerceService:
    VERSION = "1.0"
    FORMATS = ("long_video", "short_video", "comparison", "review", "story")
    COMMERCIAL_INTENTS = ("informational", "commercial", "transactional")
    PLATFORMS = ("youtube", "tiktok", "facebook", "instagram")
    MAX_TOPIC_LENGTH = 240

    def build_opportunity(self, *, topic: str, audience: str = "", demand_score: float = 0,
                          competition_score: float = 0, commercial_intent: str = "commercial",
                          monetization_score: float = 0, recommended_format: str = "comparison",
                          platforms: tuple[str, ...] | list[str] = ("youtube", "tiktok")) -> dict[str, Any]:
        topic = self._required_text(topic, "topic_required", self.MAX_TOPIC_LENGTH)
        audience = self._required_text(audience or "general audience", "audience_required", 160)
        intent = str(commercial_intent or "").strip().lower()
        if intent not in self.COMMERCIAL_INTENTS:
            raise ValueError("invalid_commercial_intent")
        output_format = str(recommended_format or "").strip().lower()
        if output_format not in self.FORMATS:
            raise ValueError("unsupported_content_format")
        selected_platforms = self._platforms(platforms)
        opportunity = CommerceOpportunity(
            topic=topic,
            audience=audience,
            commercial_intent=intent,
            demand_score=self._score(demand_score),
            competition_score=self._score(competition_score),
            monetization_score=self._score(monetization_score),
            recommended_format=output_format,
            platforms=selected_platforms,
        )
        score = self._opportunity_score(opportunity)
        return {
            "success": True,
            "engine": "kemet_creator_commerce",
            "version": self.VERSION,
            "status": "proposal",
            "opportunity": opportunity.as_dict(),
            "opportunity_score": score,
            "recommendation": self._recommendation(score, opportunity),
            "governance": self._governance(),
        }

    def build_content_plan(self, *, organization_id: int, opportunity: Mapping[str, Any],
                           product: Mapping[str, Any] | None = None, language: str = "ar") -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not isinstance(opportunity, Mapping) or not str(opportunity.get("topic") or "").strip():
            raise ValueError("opportunity_required")
        topic = str(opportunity["topic"]).strip()[: self.MAX_TOPIC_LENGTH]
        audience = str(opportunity.get("audience") or "general audience").strip()[:160]
        fmt = str(opportunity.get("recommended_format") or "comparison").strip().lower()
        if fmt not in self.FORMATS:
            raise ValueError("unsupported_content_format")
        platforms = self._platforms(opportunity.get("platforms") or self.PLATFORMS[:2])
        creative = None
        if product:
            creative = ecommerce_creative_service.build_brief(
                dict(product), objective="commercial_education", audience=audience,
                channel="web", output_type="short_video" if fmt == "short_video" else "product_showcase",
                language=language,
            )
        distribution = [
            SocialDistributionContract.plan(platform, asset_uri="pending:creator_asset",
                                            title=topic, caption=topic)
            for platform in platforms
        ]
        return {
            "success": True,
            "engine": "kemet_creator_commerce",
            "version": self.VERSION,
            "status": "approval_required",
            "organization_id": int(organization_id),
            "content": {
                "topic": topic,
                "audience": audience,
                "format": fmt,
                "language": str(language or "ar")[:12],
                "originality_required": True,
                "fact_check_required": True,
                "affiliate_disclosure_required": True,
            },
            "creative": creative,
            "distribution": distribution,
            "monetization": self._monetization_plan(opportunity),
            "kpis": self._kpis(),
            "governance": self._governance(),
        }

    @staticmethod
    def _required_text(value: Any, error: str, limit: int) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(error)
        return text[:limit]

    @staticmethod
    def _score(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("score_must_be_numeric") from exc
        if not math.isfinite(number) or number < 0 or number > 100:
            raise ValueError("score_out_of_range")
        return round(number, 2)

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
    def _opportunity_score(opportunity: CommerceOpportunity) -> float:
        intent_bonus = {"informational": 0, "commercial": 8, "transactional": 15}[opportunity.commercial_intent]
        value = (
            opportunity.demand_score * 0.35
            + (100 - opportunity.competition_score) * 0.20
            + opportunity.monetization_score * 0.45
            + intent_bonus
        )
        return round(min(100.0, max(0.0, value)), 2)

    @staticmethod
    def _recommendation(score: float, opportunity: CommerceOpportunity) -> str:
        if score >= 75:
            return "scale_candidate"
        if score >= 55:
            return "validate_with_small_experiment"
        return "do_not_scale_yet"

    @staticmethod
    def _monetization_plan(opportunity: Mapping[str, Any]) -> dict[str, Any]:
        intent = str(opportunity.get("commercial_intent") or "commercial").lower()
        channels = ["platform_ads"]
        if intent in {"commercial", "transactional"}:
            channels.extend(["affiliate", "sponsorship", "lead_generation"])
        return {
            "channels": channels,
            "affiliate": {
                "enabled": "affiliate" in channels,
                "requires_disclosure": True,
                "requires_attribution": True,
            },
            "rule": "optimize_for_revenue_per_qualified_view_not_raw_views",
        }

    @staticmethod
    def _kpis() -> list[str]:
        return [
            "qualified_views",
            "watch_time",
            "retention",
            "click_through_rate",
            "affiliate_clicks",
            "conversions",
            "revenue",
            "revenue_per_1000_qualified_views",
        ]

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "mode": "advisory",
            "read_only": True,
            "external_execution": False,
            "database_mutation": False,
            "execution_authority": False,
            "human_approval_required": True,
            "canonical_executor": "kemet_canonical_runtime",
        }

    @staticmethod
    def fingerprint(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


creator_commerce_service = CreatorCommerceService()
