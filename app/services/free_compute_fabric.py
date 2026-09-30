from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

SCHEMA = "kemet.media.free_compute_fabric.v1"
VERSION = "1.2"


def _digest(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


class FreeComputeFabricV1:
    """Advisory free-first compute registry; it never claims capacity without evidence."""

    @staticmethod
    def classify_cost(provider: dict[str, Any]) -> str:
        if provider.get("self_hosted") is True:
            return "SELF_HOSTED"
        if provider.get("free") is True and provider.get("quota_limited") is True:
            return "FREE_WITH_CAPACITY_LIMIT"
        if provider.get("free") is True:
            return "FREE"
        if provider.get("free") is False:
            return "PAID"
        return "UNKNOWN"

    def snapshot(self, providers: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        normalized = []
        for provider in providers:
            item = dict(provider)
            item.setdefault("execution_authority", False)
            item.setdefault("external_execution", False)
            item.setdefault("mcp", False)
            item.setdefault("trust", "untrusted")
            item.setdefault("free", True)
            item.setdefault("status", "UNKNOWN")
            item.setdefault("cost_classification", self.classify_cost(item))
            item.setdefault("capacity_evidence", None)
            normalized.append(item)
        ready = [p for p in normalized if self._capacity_admitted(p)]
        body = {
            "schema": SCHEMA,
            "version": VERSION,
            "captured_at": now.isoformat(),
            "policy": {
                "free_first": True,
                "configuration_is_not_capacity": True,
                "no_unverified_capacity": True,
                "no_paid_fallback": True,
                "human_approval_required": True,
            },
            "providers": normalized,
            "ready_provider_count": len(ready),
            "governance": {
                "execution_authority": False,
                "external_execution": False,
                "mcp": False,
            },
        }
        body["digest"] = _digest(body)
        return body

    @staticmethod
    def _capacity_admitted(provider: dict[str, Any]) -> bool:
        evidence = provider.get("capacity_evidence")
        if not isinstance(evidence, dict):
            return False
        if provider.get("status") != "READY" or provider.get("free") is not True:
            return False
        attestation = evidence.get("attestation") or {}
        if attestation.get("ready") is not True:
            return False
        if not evidence.get("observed_at") or not evidence.get("attestation_digest"):
            return False
        return True

    def select(self, snapshot: dict[str, Any], required_capability: str) -> dict[str, Any]:
        candidates = [
            p for p in snapshot.get("providers", [])
            if p.get("free") is True
            and required_capability in p.get("capabilities", [])
            and self._capacity_admitted(p)
        ]
        if not candidates:
            return {
                "schema": SCHEMA,
                "status": "WAITING_FOR_FREE_CAPACITY",
                "required_capability": required_capability,
                "selected_provider": None,
                "execution_authority": False,
                "external_execution": False,
                "mcp": False,
                "cost_classification": "UNKNOWN",
            }
        selected = sorted(candidates, key=lambda p: (p.get("queue_depth", 10**9), p.get("provider_id", "")))[0]
        return {
            "schema": SCHEMA,
            "status": "FREE_CAPACITY_READY",
            "required_capability": required_capability,
            "selected_provider": selected,
            "cost_classification": self.classify_cost(selected),
            "execution_authority": False,
            "external_execution": False,
            "mcp": False,
        }
