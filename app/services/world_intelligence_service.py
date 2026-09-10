from dataclasses import dataclass, asdict
from typing import Iterable, Optional
from urllib.parse import urlparse

@dataclass(frozen=True)
class IntelligenceItem:
    title: str
    source: str
    url: str
    category: str
    confidence: float = 0.0
    published_at: Optional[str] = None

class WorldIntelligenceService:
    VERSION = "1.0"
    CATEGORIES = (
        "ai", "business", "markets", "technology", "competitors",
        "regulation", "github", "trends",
    )

    def normalize(self, items: Iterable[dict]) -> list[dict]:
        normalized = []
        for raw in items or []:
            title = str(raw.get("title") or "").strip()
            source = str(raw.get("source") or "").strip()
            url = str(raw.get("url") or "").strip()
            category = str(raw.get("category") or "general").strip().lower()
            if not title or not source or not url:
                continue
            confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.0))))
            normalized.append(asdict(IntelligenceItem(title, source, url, category, confidence, raw.get("published_at"))))
        return normalized

    def verify(self, items: Iterable[dict]) -> list[dict]:
        verified = []
        for item in self.normalize(items):
            parsed = urlparse(item["url"])
            valid_url = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
            source_ok = bool(item["source"])
            item["verified"] = bool(valid_url and source_ok and item["confidence"] >= 0.5)
            item["verification_reason"] = "source_and_url_valid" if item["verified"] else "insufficient_source_confidence"
            verified.append(item)
        return verified

    def rank(self, items: Iterable[dict]) -> list[dict]:
        verified = self.verify(items)
        return sorted(
            verified,
            key=lambda item: (item["verified"], item["confidence"], item["title"]),
            reverse=True,
        )

    def classify_recommendation(self, item: dict) -> str:
        if not item.get("verified") or item.get("confidence", 0.0) < 0.5:
            return "WATCH"
        category = item.get("category", "general")
        if category in {"ai", "technology", "github"} and item.get("confidence", 0.0) >= 0.9:
            return "INTEGRATE"
        if category in {"competitors", "regulation", "markets", "business"} and item.get("confidence", 0.0) >= 0.9:
            return "BUILD"
        return "WATCH"

    def brief(self, items: Iterable[dict], limit: int = 10) -> dict:
        ranked = self.rank(items)[:max(1, min(int(limit), 50))]
        for item in ranked:
            item["recommendation"] = self.classify_recommendation(item)
        return {
            "engine": "kemet_world_intelligence",
            "version": self.VERSION,
            "status": "ok",
            "items": ranked,
            "governance": {
                "read_only": True, "advisory": True,
                "external_execution": False, "database_mutation": False,
                "auto_execute": False,
            },
        }

world_intelligence = WorldIntelligenceService()
