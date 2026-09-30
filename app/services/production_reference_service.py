"""Kemet-native golden reference registry for continuity-controlled media production."""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any, Mapping


class ProductionReferenceService:
    VERSION = "1.0"
    SCHEMA = "kemet.media.golden_reference_pack.v1"

    def build_pack(self, *, organization_id: int, project_id: str,
                   visual_direction: Mapping[str, Any], characters: list[Mapping[str, Any]],
                   worlds: list[Mapping[str, Any]], assets: list[Mapping[str, Any]] | None = None, production_profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not isinstance(visual_direction, Mapping) or not visual_direction.get("id"):
            raise ValueError("visual_direction_required")
        profile = dict(production_profile or {})
        if profile and profile.get("schema") != "kemet.visual.production_profile.v1":
            raise ValueError("production_profile_invalid")
        if profile and profile.get("profile_id") != str(visual_direction.get("id")):
            raise ValueError("production_profile_direction_mismatch")
        char_refs = [self._reference(x, "character") for x in characters]
        world_refs = [self._reference(x, "world") for x in worlds]
        asset_refs = [self._reference(x, "asset") for x in (assets or [])]
        payload = {
            "schema": self.SCHEMA,
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "visual_direction": dict(visual_direction),
            "production_profile": dict(production_profile or {}),
            "character_references": char_refs,
            "world_references": world_refs,
            "asset_references": asset_refs,
            "invariants": {
                "character_identity": True,
                "world_geography": True,
                "visual_language": True,
                "reference_first_generation": True,
                "drift_requires_review": True,
            },
            "provider_independent": True,
            "source_of_truth": "canonical_production_state",
            "governance": {"human_approval_required": True, "external_execution": False, "mcp": False},
        }
        payload["digest"] = self._digest(payload)
        return payload

    @staticmethod
    def _reference(value: Mapping[str, Any], kind: str) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError(f"{kind}_reference_invalid")
        ref_id = str(value.get("id") or value.get(f"{kind}_id") or "").strip()
        digest = str(value.get("digest") or "").strip()
        version = value.get("version")
        if not ref_id or not digest or not version:
            raise ValueError(f"{kind}_reference_exact_binding_required")
        return {"id": ref_id, "version": int(version), "digest": digest,
                "uri": value.get("uri"), "role": value.get("role") or kind}

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


production_reference_service = ProductionReferenceService()
