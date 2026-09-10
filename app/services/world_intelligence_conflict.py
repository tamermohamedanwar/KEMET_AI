from collections import defaultdict


class WorldIntelligenceConflictDetector:
    VERSION = "1.0"

    def detect(self, items):
        groups = defaultdict(list)
        for item in items or []:
            key = (str(item.get("category", "general")).strip().lower(),
                   str(item.get("title", "")).strip().lower())
            if key[1]:
                groups[key].append(item)
        conflicts = []
        for (category, title), group in groups.items():
            trusts = [float(item.get("source_trust", 0.4)) for item in group]
            confidences = [float(item.get("confidence", 0)) for item in group]
            if len(group) > 1 and max(trusts) - min(trusts) >= 0.25:
                conflicts.append({
                    "category": category,
                    "title": title,
                    "source_count": len(group),
                    "trust_spread": round(max(trusts) - min(trusts), 4),
                    "confidence": round(sum(confidences) / len(confidences), 4),
                    "status": "review_required",
                })
        return {
            "engine": "kemet_world_intelligence_conflict",
            "version": self.VERSION,
            "status": "ok",
            "conflicts": conflicts,
            "governance": {
                "read_only": True,
                "advisory": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
            },
        }


world_intelligence_conflict_detector = WorldIntelligenceConflictDetector()
