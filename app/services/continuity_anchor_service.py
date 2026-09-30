"""Canonical continuity anchors for provider-independent cinematic generation."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping


class ContinuityAnchorService:
    VERSION = "1.0"
    SCHEMA = "kemet.cinematic.continuity_anchor.v1"
    ANCHOR_KINDS = ("initial_frame", "last_frame", "keyframe", "reference", "scene_state")

    def build_anchor(
        self,
        *,
        organization_id: int,
        project_id: str,
        scene_id: str,
        shot_id: str,
        anchor_kind: str,
        asset_id: str,
        asset_version: int,
        asset_digest: str,
        source_shot_id: str | None = None,
        frame_index: int | None = None,
        provider_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._org(organization_id)
        kind = str(anchor_kind).strip()
        if kind not in self.ANCHOR_KINDS:
            raise ValueError("continuity_anchor_kind_invalid")
        if not asset_id or int(asset_version or 0) <= 0 or not asset_digest:
            raise ValueError("continuity_anchor_exact_binding_required")
        payload = {
            "schema": self.SCHEMA,
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "scene_id": str(scene_id),
            "shot_id": str(shot_id),
            "anchor_kind": kind,
            "asset": {
                "asset_id": str(asset_id),
                "version": int(asset_version),
                "digest": str(asset_digest),
            },
            "source_shot_id": str(source_shot_id) if source_shot_id else None,
            "frame_index": frame_index,
            "provider_id": provider_id,
            "metadata": dict(metadata or {}),
            "policy": {
                "immutable": True,
                "provider_independent": True,
                "cross_provider_allowed": True,
                "drift_requires_review": True,
            },
        }
        return self._finalize(payload)

    def build_shot_continuity(
        self,
        *,
        organization_id: int,
        project_id: str,
        scene_id: str,
        shot: Mapping[str, Any],
        incoming: list[Mapping[str, Any]] | None = None,
        outgoing: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._org(organization_id)
        if not shot.get("shot_id") or not shot.get("canonical_shot_digest"):
            raise ValueError("canonical_shot_binding_required")
        incoming_anchors = [self._exact_anchor(x) for x in (incoming or [])]
        outgoing_anchors = [self._exact_anchor(x) for x in (outgoing or [])]
        payload = {
            "schema": "kemet.cinematic.shot_continuity.v1",
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "scene_id": str(scene_id),
            "shot_id": str(shot["shot_id"]),
            "canonical_shot_digest": str(shot["canonical_shot_digest"]),
            "incoming_anchors": incoming_anchors,
            "outgoing_anchors": outgoing_anchors,
            "continuity_contract": {
                "character_identity_locked": True,
                "world_geometry_locked": True,
                "wardrobe_locked": True,
                "lighting_transition_checked": True,
                "camera_transition_checked": True,
                "provider_switch_requires_anchor": True,
                "chunk_transition_requires_anchor": True,
            },
        }
        return self._finalize(payload)

    @staticmethod
    def _exact_anchor(anchor: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(anchor, Mapping):
            raise ValueError("continuity_anchor_required")
        if not anchor.get("digest") or not anchor.get("anchor_kind"):
            raise ValueError("continuity_anchor_exact_binding_required")
        asset = anchor.get("asset") or {}
        if not asset.get("asset_id") or not asset.get("version") or not asset.get("digest"):
            raise ValueError("continuity_anchor_asset_binding_required")
        return {
            "anchor_id": anchor.get("anchor_id"),
            "anchor_kind": anchor["anchor_kind"],
            "asset": {
                "asset_id": asset["asset_id"],
                "version": int(asset["version"]),
                "digest": asset["digest"],
            },
            "digest": anchor["digest"],
            "shot_id": anchor.get("shot_id"),
            "source_shot_id": anchor.get("source_shot_id"),
        }

    @staticmethod
    def _org(value: Any) -> None:
        if int(value or 0) <= 0:
            raise ValueError("organization_required")

    @staticmethod
    def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
        digest = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
        payload["digest"] = digest
        payload["anchor_id"] = f"anchor-{digest[:16]}"
        payload["governance"] = {
            "execution_authority": False,
            "external_execution": False,
            "human_approval_required": True,
            "mcp": False,
        }
        return payload


continuity_anchor_service = ContinuityAnchorService()
