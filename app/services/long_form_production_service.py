"""Kemet-native long-form Shot Graph, Continuity Graph, Editorial Timeline, and Production Manifest."""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any, Mapping


class LongFormProductionService:
    VERSION = "1.1"
    SHOT_GRAPH_SCHEMA = "kemet.cinematic.shot_graph.v1"
    CONTINUITY_GRAPH_SCHEMA = "kemet.cinematic.continuity_graph.v1"
    EDITORIAL_SCHEMA = "kemet.cinematic.editorial_timeline.v1"
    PRODUCTION_MANIFEST_SCHEMA = "kemet.cinematic.production_manifest.v1"

    def build_production_manifest(
        self, *, organization_id: int, project_id: str,
        project: Mapping[str, Any], seasons: list[Mapping[str, Any]] | None = None,
        episodes: list[Mapping[str, Any]] | None = None,
        sequences: list[Mapping[str, Any]] | None = None,
        scenes: list[Mapping[str, Any]] | None = None,
        shots: list[Mapping[str, Any]] | None = None,
        characters: list[Mapping[str, Any]] | None = None,
        worlds: list[Mapping[str, Any]] | None = None,
        assets: list[Mapping[str, Any]] | None = None,
        bibles: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build one resumable hierarchical production manifest; planning only."""
        self._org(organization_id)
        if not str(project.get("project_id") or project_id).strip():
            raise ValueError("project_required")

        def nodes(items: list[Mapping[str, Any]], kind: str) -> list[dict[str, Any]]:
            result = []
            for item in items:
                item_id = str(item.get(f"{kind}_id") or item.get("id") or "").strip()
                if not item_id:
                    raise ValueError(f"{kind}_id_required")
                result.append({
                    "id": item_id,
                    "kind": kind,
                    "version": int(item.get("version") or 1),
                    "digest": str(item.get("digest") or item.get("canonical_shot_digest") or "").strip(),
                })
            return result

        hierarchy = {
            "project": nodes([project], "project"),
            "season": nodes(list(seasons or []), "season"),
            "episode": nodes(list(episodes or []), "episode"),
            "sequence": nodes(list(sequences or []), "sequence"),
            "scene": nodes(list(scenes or []), "scene"),
            "shot": nodes(list(shots or []), "shot"),
            "asset": nodes(list(assets or []), "asset"),
        }
        for required_kind in ("season", "episode", "sequence", "scene", "shot"):
            if hierarchy[required_kind] and any(not n["digest"] for n in hierarchy[required_kind]):
                raise ValueError(f"{required_kind}_digest_required")

        identity = {
            "characters": nodes(list(characters or []), "character"),
            "worlds": nodes(list(worlds or []), "world"),
            "bibles": dict(bibles or {}),
        }
        payload = {
            "schema": self.PRODUCTION_MANIFEST_SCHEMA,
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "hierarchy": hierarchy,
            "identity": identity,
            "production_strategy": {
                "hierarchical_generation": True,
                "chunked_generation": True,
                "checkpointing": True,
                "resumable": True,
                "incremental_rendering": True,
                "targeted_regeneration": True,
                "full_project_regeneration": False,
            },
            "continuity": {
                "character_identity_persistent": True,
                "world_identity_persistent": True,
                "cross_episode_state": True,
                "cross_scene_state": True,
                "canonical_references_required": True,
                "drift_requires_local_repair": True,
            },
            "repair_policy": {
                "failure_localization_required": True,
                "affected_artifacts_only": True,
                "upstream_state_preserved": True,
                "downstream_impact_recomputed": True,
            },
            "source_of_truth": "canonical_production_state",
            "provider_independent": True,
            "planning_only": True,
            "governance": {
                "human_approval_required": True,
                "execution_authority": False,
                "external_execution": False,
                "mcp": False,
            },
        }
        return self._finalize(payload)

    def build_shot_graph(self, *, organization_id: int, project_id: str, shots: list[Mapping[str, Any]]) -> dict[str, Any]:
        self._org(organization_id)
        nodes = []
        edges = []
        for index, shot in enumerate(shots):
            shot_id = str(shot.get("shot_id") or "")
            digest = str(shot.get("canonical_shot_digest") or "")
            if not shot_id or not digest:
                raise ValueError("canonical_shot_binding_required")
            nodes.append({"id": shot_id, "kind": "shot", "sequence": index + 1, "digest": digest})
            if index:
                edges.append({"from": str(shots[index - 1]["shot_id"]), "to": shot_id, "relation": "sequence"})
        return self._finalize({"schema": self.SHOT_GRAPH_SCHEMA, "version": 1, "organization_id": int(organization_id), "project_id": str(project_id), "nodes": nodes, "edges": edges, "canonical": True, "provider_independent": True})

    def build_continuity_graph(self, *, organization_id: int, project_id: str, shots: list[Mapping[str, Any]], anchors: list[Mapping[str, Any]]) -> dict[str, Any]:
        self._org(organization_id)
        anchor_by_shot = {}
        for anchor in anchors:
            shot_id = str(anchor.get("shot_id") or anchor.get("source_shot_id") or "")
            if not shot_id or not anchor.get("digest"):
                raise ValueError("continuity_anchor_exact_binding_required")
            anchor_by_shot.setdefault(shot_id, []).append(dict(anchor))
        nodes = [{"id": str(s["shot_id"]), "kind": "shot", "shot_digest": str(s["canonical_shot_digest"]), "anchors": anchor_by_shot.get(str(s["shot_id"]), [])} for s in shots]
        edges = []
        for index in range(1, len(shots)):
            previous = str(shots[index - 1]["shot_id"])
            current = str(shots[index]["shot_id"])
            if not anchor_by_shot.get(current) and not anchor_by_shot.get(previous):
                raise ValueError("continuity_transition_anchor_required")
            edges.append({"from": previous, "to": current, "relation": "continuity", "requires_anchor": True})
        return self._finalize({"schema": self.CONTINUITY_GRAPH_SCHEMA, "version": 1, "organization_id": int(organization_id), "project_id": str(project_id), "nodes": nodes, "edges": edges, "policy": {"provider_switch_requires_anchor": True, "chunk_transition_requires_anchor": True, "drift_requires_review": True}})

    def build_editorial_timeline(self, *, organization_id: int, project_id: str, shots: list[Mapping[str, Any]], transitions: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        cursor = 0.0
        clips = []
        for index, shot in enumerate(shots):
            duration = float(shot.get("duration_seconds") or 0)
            if duration <= 0:
                raise ValueError("editorial_duration_required")
            clips.append({"shot_id": str(shot["shot_id"]), "sequence": index + 1, "start_seconds": cursor, "duration_seconds": duration, "end_seconds": cursor + duration, "artifact_binding_required": True})
            cursor += duration
        payload = {"schema": self.EDITORIAL_SCHEMA, "version": 1, "organization_id": int(organization_id), "project_id": str(project_id), "duration_seconds": cursor, "clips": clips, "transitions": [dict(x) for x in (transitions or [])], "assembly": {"mode": "timeline", "concatenation_only": False, "continuity_graph_required": True, "qa_required": True}}
        return self._finalize(payload)

    @staticmethod
    def _org(value: Any) -> None:
        if int(value or 0) <= 0:
            raise ValueError("organization_required")

    @staticmethod
    def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
        payload["digest"] = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
        payload["governance"] = {**payload.get("governance", {}), "human_approval_required": True, "execution_authority": False, "external_execution": False, "mcp": False}
        return payload


long_form_production_service = LongFormProductionService()
