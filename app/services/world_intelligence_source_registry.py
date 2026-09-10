from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceProfile:
    name: str
    trust: float
    categories: tuple[str, ...] = ()
    tier: str = "standard"


class WorldIntelligenceSourceRegistry:
    VERSION = "1.0"

    DEFAULTS = (
        SourceProfile("official", 0.98, ("business", "regulation", "technology"), "primary"),
        SourceProfile("github", 0.95, ("github", "technology"), "primary"),
        SourceProfile("major_news", 0.90, ("business", "markets", "trends"), "secondary"),
        SourceProfile("research", 0.93, ("ai", "technology", "trends"), "primary"),
        SourceProfile("unknown", 0.40, (), "unverified"),
    )

    def __init__(self, profiles=None):
        self._profiles = {p.name: p for p in (profiles or self.DEFAULTS)}

    @staticmethod
    def source_key(item):
        source = str(item.get("source", "")).strip().lower()
        host = urlparse(str(item.get("url", "")).strip()).netloc.lower()
        return source or host or "unknown"

    def profile(self, item):
        key = self.source_key(item)
        if key in self._profiles:
            return self._profiles[key]
        host = urlparse(str(item.get("url", "")).strip()).netloc.lower()
        for name, profile in self._profiles.items():
            if name != "unknown" and (name in host or name in key):
                return profile
        return self._profiles["unknown"]

    def enrich(self, items):
        enriched = []
        for item in items or []:
            profile = self.profile(item)
            value = dict(item)
            value["source_key"] = self.source_key(item)
            value["source_trust"] = profile.trust
            value["source_tier"] = profile.tier
            enriched.append(value)
        return enriched


world_intelligence_source_registry = WorldIntelligenceSourceRegistry()
