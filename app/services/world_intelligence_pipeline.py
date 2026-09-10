from hashlib import sha256
from typing import Iterable
from app.services.world_intelligence_conflict import world_intelligence_conflict_detector
from app.services.world_intelligence_service import world_intelligence
from app.services.world_intelligence_source_registry import world_intelligence_source_registry


class WorldIntelligencePipeline:
    VERSION = "1.0"

    @staticmethod
    def _fingerprint(item):
        value = "|".join((item.get("title", "").strip().lower(), item.get("url", "").strip().lower()))
        return sha256(value.encode("utf-8")).hexdigest()

    def process(self, items: Iterable[dict], limit: int = 20) -> dict:
        source_items = list(items or [])
        enriched = world_intelligence_source_registry.enrich(source_items)
        seen = set()
        unique = []
        for item in enriched:
            fingerprint = self._fingerprint(item)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            unique.append(item)
        conflicts = world_intelligence_conflict_detector.detect(unique)
        brief = world_intelligence.brief(unique, limit=limit)
        enriched_by_fingerprint = {
            self._fingerprint(item): item for item in unique
        }
        for item in brief["items"]:
            source = enriched_by_fingerprint.get(self._fingerprint(item), {})
            for key in ("source_key", "source_trust", "source_tier"):
                if key in source:
                    item[key] = source[key]
            item["fingerprint"] = self._fingerprint(item)
        return {
            "engine": "kemet_world_intelligence_pipeline",
            "version": self.VERSION,
            "status": "ok",
            "input_count": len(source_items),
            "unique_count": len(unique),
            "items": brief["items"],
            "conflicts": conflicts["conflicts"],
            "governance": brief["governance"],
        }


world_intelligence_pipeline = WorldIntelligencePipeline()
