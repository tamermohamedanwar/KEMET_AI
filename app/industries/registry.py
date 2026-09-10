from __future__ import annotations

from copy import deepcopy

from app.industries.packs import INDUSTRY_PACKS


class IndustryRegistry:
    def __init__(self, packs=None):
        self._packs = dict(packs or INDUSTRY_PACKS)

    def exists(self, industry_id: str) -> bool:
        return str(industry_id or "").strip().lower() in self._packs

    def get(self, industry_id: str):
        key = str(industry_id or "").strip().lower()
        pack = self._packs.get(key)

        if pack is None:
            return None

        result = deepcopy(pack)
        result["id"] = key
        return result

    def list(self):
        return [
            {
                "id": industry_id,
                "name": pack.get("name", industry_id),
                "description": pack.get("description", ""),
            }
            for industry_id, pack in self._packs.items()
        ]

    def entities(self, industry_id: str):
        pack = self.get(industry_id)
        return pack.get("entities", []) if pack else []

    def actions(self, industry_id: str):
        pack = self.get(industry_id)
        return pack.get("actions", []) if pack else []

    def workforce(self, industry_id: str):
        pack = self.get(industry_id)
        return pack.get("workforce", []) if pack else []

    def metrics(self, industry_id: str):
        pack = self.get(industry_id)
        return pack.get("metrics", []) if pack else []


industry_registry = IndustryRegistry()
