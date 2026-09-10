from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

@dataclass(frozen=True)
class MarketplaceItem:
    item_id: str
    name: str
    category: str
    version: str = "1.0"
    description: str = ""
    capabilities: tuple = ()
    price: float = 0.0
    currency: str = "USD"
    enabled: bool = True
    requires_approval: bool = True

class MarketplaceEngine:
    VALID_CATEGORIES = {"automation", "agent", "template", "integration"}

    def __init__(self, items: Optional[List[MarketplaceItem]] = None):
        self._items: Dict[str, MarketplaceItem] = {}
        for item in items or []:
            self.register(item)

    def register(self, item: MarketplaceItem) -> Dict:
        if not item.item_id:
            raise ValueError("item_id is required")
        if item.category not in self.VALID_CATEGORIES:
            raise ValueError("unsupported marketplace category")
        if item.price < 0:
            raise ValueError("price cannot be negative")
        self._items[item.item_id] = item
        return {"ok": True, "item_id": item.item_id, "registered": True}

    def list_items(self, category=None, enabled_only=True) -> List[Dict]:
        items = list(self._items.values())
        if category:
            items = [x for x in items if x.category == category]
        if enabled_only:
            items = [x for x in items if x.enabled]
        items.sort(key=lambda x: (x.category, x.name.lower()))
        return [asdict(x) for x in items]

    def search(self, query, category=None) -> List[Dict]:
        q = (query or "").strip().lower()
        if not q:
            return self.list_items(category=category)

        results = []
        for item in self._items.values():
            if not item.enabled:
                continue
            if category and item.category != category:
                continue
            haystack = " ".join([
                item.item_id,
                item.name,
                item.description,
                item.category,
                " ".join(item.capabilities),
            ]).lower()
            if q in haystack:
                results.append(asdict(item))

        results.sort(key=lambda x: (x["name"].lower(), x["item_id"]))
        return results

    def resolve(self, item_id):
        item = self._items.get(item_id)
        if not item or not item.enabled:
            return None
        return asdict(item)

    def build_activation_plan(self, item_id):
        item = self._items.get(item_id)

        if not item:
            return {"ok": False, "status": "not_found", "item_id": item_id}

        if not item.enabled:
            return {"ok": False, "status": "disabled", "item_id": item_id}

        return {
            "ok": True,
            "status": "waiting_approval" if item.requires_approval else "ready",
            "engine": "kemet_marketplace",
            "version": "1.0",
            "item": asdict(item),
            "requires_approval": item.requires_approval,
            "external_execution": False,
            "database_mutation": False,
        }

    def summary(self):
        items = list(self._items.values())
        return {
            "total": len(items),
            "enabled": sum(1 for x in items if x.enabled),
            "categories": {
                c: sum(1 for x in items if x.category == c)
                for c in sorted(self.VALID_CATEGORIES)
            },
            "mode": "advisory",
            "external_execution": False,
            "database_mutation": False,
        }
