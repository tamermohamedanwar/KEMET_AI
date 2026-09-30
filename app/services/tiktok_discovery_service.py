from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True)
class TikTokDiscoveryQuery:
    organization_id: int
    topic: str
    region_code: str = "EG"
    language: str = "ar"
    max_results: int = 20


class TikTokDiscoveryService:
    VERSION = "1.0"
    SOURCE = "tiktok_research_api"

    def plan(self, query: TikTokDiscoveryQuery) -> dict[str, Any]:
        if query.organization_id <= 0:
            return self._blocked("organization_required")
        topic = query.topic.strip()
        if not topic:
            return self._blocked("topic_required")
        if not 1 <= query.max_results <= 100:
            return self._blocked("max_results_out_of_range")
        plan = {
            "source": self.SOURCE,
            "query": {"topic": topic, "region_code": query.region_code.upper(), "language": query.language, "max_results": query.max_results},
            "signals": ["view_count", "like_count", "comment_count", "share_count", "video_duration", "hashtag_names", "create_time", "username"],
            "read_only": True,
            "public_content_only": True,
            "credentials_exposed": False,
            "execution_authority": False,
            "canonical_runtime_only": True,
        }
        plan["plan_digest"] = sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
        return {"success": True, "status": "planned", "plan": plan}

    def rank(self, query: TikTokDiscoveryQuery, videos: list[dict[str, Any]]) -> dict[str, Any]:
        if query.organization_id <= 0:
            return self._blocked("organization_required")
        ranked = []
        for video in videos[:100]:
            if not isinstance(video, dict) or not video.get("id"):
                continue
            views = max(int(video.get("view_count") or 0), 0)
            likes = max(int(video.get("like_count") or 0), 0)
            comments = max(int(video.get("comment_count") or 0), 0)
            shares = max(int(video.get("share_count") or 0), 0)
            engagement = (likes + comments * 2 + shares * 3) / views if views else 0.0
            score = min(100.0, engagement * 1000.0 + min(views / 100000.0, 20.0))
            ranked.append({"video_id": str(video["id"]), "creator": video.get("username"), "views": views, "engagement_rate": round(engagement, 6), "opportunity_score": round(score, 2), "hashtags": list(video.get("hashtag_names") or []), "duration_seconds": video.get("video_duration"), "evidence_source": self.SOURCE})
        ranked.sort(key=lambda item: item["opportunity_score"], reverse=True)
        return {"success": True, "status": "ranked", "source": self.SOURCE, "results": ranked, "verified": False, "read_only": True, "execution_authority": False}

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "error": error, "execution_authority": False, "credentials_exposed": False}


tiktok_discovery_service = TikTokDiscoveryService()
