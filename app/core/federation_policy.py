from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FederationPolicy:
    organization_id: int | str | None
    allowed_providers: frozenset[str] | None = None
    preferred_provider: str | None = None
    required_capabilities: frozenset[str] = frozenset()
    allowed_models: frozenset[str] | None = None
    default_model: str | None = None

    def provider_allowed(self, provider_id: str) -> bool:
        return self.allowed_providers is None or provider_id in self.allowed_providers

    def model_allowed(self, model: str | None) -> bool:
        return model is None or self.allowed_models is None or model in self.allowed_models


class FederationPolicyRegistry:
    VERSION = "1.0"

    def __init__(self, raw: dict | None = None):
        self._raw = raw if raw is not None else self._load_env()

    def snapshot(self) -> dict:
        return {"version": self.VERSION, "scoped_organizations": sorted((self._raw.get("organizations") or {}).keys()), "has_default": bool(self._raw.get("default"))}

    @staticmethod
    def _load_env() -> dict:
        raw = os.getenv("KEMET_FEDERATION_POLICY_JSON", "").strip()
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def for_organization(self, organization_id: int | str | None) -> FederationPolicy:
        defaults = self._raw.get("default", {})
        scoped = self._raw.get("organizations", {}).get(str(organization_id), {})
        data = {**defaults, **(scoped if isinstance(scoped, dict) else {})}
        return FederationPolicy(
            organization_id=organization_id,
            allowed_providers=self._as_set(data.get("allowed_providers")),
            preferred_provider=data.get("preferred_provider"),
            required_capabilities=frozenset(self._as_list(data.get("required_capabilities"))),
            allowed_models=self._as_set(data.get("allowed_models")),
            default_model=data.get("default_model"),
        )

    @staticmethod
    def _as_list(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set, frozenset)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @classmethod
    def _as_set(cls, value: object) -> frozenset[str] | None:
        values = cls._as_list(value)
        return frozenset(values) if values else None


federation_policy = FederationPolicyRegistry()
