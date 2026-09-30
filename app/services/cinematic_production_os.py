"""Kemet-native Cinematic Production OS planning boundary."""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any, Mapping

class CinematicProductionOS:
    VERSION = "2.1"
    PRODUCTION_GRAPH_SCHEMA = "kemet.cinematic.production_graph.v1"

    GRAPH_STATES = ("PLANNED", "READY", "BLOCKED", "RUNNING", "CHECKPOINTED", "COMPLETED", "FAILED", "INVALIDATED", "REPAIR_REQUIRED")

    def build_canonical_graph(
        self, *, state: Mapping[str, Any], production_spec: Mapping[str, Any],
        capability_requirements: list[Mapping[str, Any]] | None = None,
        routing_decision: Mapping[str, Any] | None = None,
        memory: Mapping[str, Any] | None = None,
        characters: list[Mapping[str, Any]] | None = None,
        worlds: list[Mapping[str, Any]] | None = None,
        project: Mapping[str, Any] | None = None,
        season: Mapping[str, Any] | None = None,
        episode: Mapping[str, Any] | None = None,
        sequences: list[Mapping[str, Any]] | None = None,
        scenes: list[Mapping[str, Any]] | None = None,
        shots: list[Mapping[str, Any]] | None = None,
        assets: list[Mapping[str, Any]] | None = None,
        audio: list[Mapping[str, Any]] | None = None,
        timeline: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if state.get("source_of_truth") != "canonical_production_state":
            raise ValueError("canonical_production_state_required")
        if not isinstance(production_spec, Mapping) or not production_spec.get("digest"):
            raise ValueError("production_spec_exact_binding_required")
        if int(production_spec.get("organization_id") or 0) != int(state["organization_id"]):
            raise ValueError("production_spec_tenant_mismatch")
        requirements = [dict(x) for x in (capability_requirements or [])]
        route = dict(routing_decision or {})
        states = [str(x.get("state") or x.get("status") or "") for x in requirements]
        blocking = [dict(x) for x in requirements if str(x.get("state") or x.get("status") or "") in {"HARDWARE_LIMITED", "WAITING_FOR_FREE_CAPACITY", "NOT_IMPLEMENTED", "BLOCKED"}]
        graph_state = "BLOCKED" if blocking else "READY" if requirements and all(s == "READY" for s in states) else "PLANNED"
        def node(node_id, kind, status="PLANNED", data=None):
            item = {"id": str(node_id), "kind": str(kind), "status": str(status)}
            if data:
                item.update(dict(data))
            return item
        nodes = [
            node(project.get("project_id") if project else state.get("project_id"), "project", "CHECKPOINTED", {"digest": (project or {}).get("digest")}),
        ]
        if season: nodes.append(node(season.get("season_id") or season.get("id"), "season", "CHECKPOINTED", {"digest": season.get("digest")}))
        if episode: nodes.append(node(episode.get("episode_id") or episode.get("id"), "episode", "CHECKPOINTED", {"digest": episode.get("digest")}))
        for collection, kind in ((sequences or [], "sequence"), (scenes or [], "scene"), (shots or [], "shot"), (assets or [], "asset"), (audio or [], "audio")):
            for item in collection:
                item_id = item.get(f"{kind}_id") or item.get("id") or item.get("shot_id")
                if item_id:
                    nodes.append(node(item_id, kind, str(item.get("status") or "PLANNED"), {"digest": item.get("digest") or item.get("canonical_shot_digest")}))
        nodes.extend([
            node("memory", "production_memory", "BOUND" if memory else "PLANNED", {"digest": (memory or {}).get("digest")}),
            node("capabilities", "capability_requirements", "BLOCKED" if blocking else "BOUND", {"blocking": blocking}),
            node("routing", "generation_router", "BLOCKED" if blocking else "PLANNED", {"decision": route}),
            node("generation", "generation", "BLOCKED" if blocking else "PLANNED"),
            node("timeline", "timeline", "CHECKPOINTED" if timeline else "PLANNED", {"digest": (timeline or {}).get("digest")}),
            node("qa", "qa", "PLANNED"),
            node("artifact", "artifact", "PLANNED"),
        ])
        edges = []
        def chain(items):
            for a, b in zip(items, items[1:]):
                edges.append([a, b])
        hierarchy = [nodes[0]["id"]]
        for kind in ("season", "episode", "sequence", "scene", "shot", "asset", "audio"):
            ids = [n["id"] for n in nodes if n["kind"] == kind]
            if ids:
                hierarchy.append(ids[0])
        chain(hierarchy)
        for n in nodes:
            if n["kind"] in {"shot", "scene", "asset", "audio"}:
                edges.append(["memory", n["id"]])
        edges += [["capabilities", "routing"], ["routing", "generation"], ["generation", "qa"], ["qa", "timeline"], ["timeline", "artifact"]]
        payload = {
            "schema": self.PRODUCTION_GRAPH_SCHEMA, "version": 2,
            "organization_id": int(state["organization_id"]), "project_id": str(state["project_id"]),
            "state_digest": str(state["digest"]), "production_spec_digest": str(production_spec["digest"]),
            "content_intent": str(production_spec.get("content_intent") or ""),
            "language": production_spec.get("language"), "dialect": production_spec.get("dialect"),
            "graph_state": graph_state, "allowed_states": list(self.GRAPH_STATES),
            "nodes": nodes, "edges": edges, "capability_requirements": requirements,
            "blocking_capabilities": blocking, "routing_decision": route,
            "memory_digest": (memory or {}).get("digest"),
            "checkpointing": True, "resumable": True, "dependency_tracking": True,
            "targeted_regeneration": True, "downstream_reqa": True, "upstream_preservation": True,
            "provider_independent": True, "source_of_truth": "canonical_production_state",
            "prompts_are_derived": True,
            "governance": {"human_approval_required": True, "execution_authority": False, "external_execution": False, "mcp": False},
        }
        payload["digest"] = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
        return payload

    def build_graph(self, *, state: Mapping[str, Any], golden_reference: Mapping[str, Any] | None = None,
                    scenes: list[Mapping[str, Any]] | None = None,
                    shots: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        if state.get("source_of_truth") != "canonical_production_state":
            raise ValueError("canonical_production_state_required")
        nodes = [
            {"id": "intent", "kind": "intent", "status": "canonical"},
            {"id": "visual_direction", "kind": "visual_direction", "status": "selected" if state.get("visual_direction") else "pending"},
            {"id": "golden_reference", "kind": "golden_reference", "status": "bound" if golden_reference else "pending"},
            {"id": "character_identity", "kind": "character_identity", "status": "reference_bound" if golden_reference and golden_reference.get("character_references") else "pending"},
            {"id": "character_plates", "kind": "character_reference_plates", "status": "derived"},
            {"id": "world_continuity", "kind": "world_continuity", "status": "reference_bound" if golden_reference and golden_reference.get("world_references") else "pending"},
            {"id": "world_plates", "kind": "world_reference_plates", "status": "derived"},
            {"id": "story", "kind": "story", "status": "pending"},
            {"id": "shot_director", "kind": "shot_plan", "status": "bound" if shots else "pending"},
            {"id": "storyboard", "kind": "storyboard", "status": "derived"},
            {"id": "previs", "kind": "previs", "status": "pending"},
            {"id": "continuity_anchor", "kind": "continuity_anchor", "status": "required"},
            {"id": "shot_graph", "kind": "shot_graph", "status": "canonical"},
            {"id": "continuity_graph", "kind": "continuity_graph", "status": "canonical"},
            {"id": "generation_router", "kind": "generation_router", "status": "derived"},
            {"id": "generation", "kind": "generation", "status": "derived"},
            {"id": "qa", "kind": "cinematic_qa", "status": "pending"},
            {"id": "editorial_timeline", "kind": "editorial_timeline", "status": "canonical"},
            {"id": "repair", "kind": "targeted_repair", "status": "pending"},
            {"id": "final", "kind": "final_artifact", "status": "pending"},
        ]
        edges = [
            ["intent", "visual_direction"], ["visual_direction", "golden_reference"],
            ["golden_reference", "character_identity"], ["character_identity", "character_plates"],
            ["golden_reference", "world_continuity"], ["world_continuity", "world_plates"],
            ["character_plates", "story"], ["world_plates", "story"],
            ["story", "shot_director"], ["shot_director", "storyboard"],
            ["storyboard", "previs"], ["previs", "continuity_anchor"],
            ["continuity_anchor", "shot_graph"], ["shot_graph", "continuity_graph"],
            ["continuity_graph", "generation_router"], ["generation_router", "generation"],
            ["generation", "qa"], ["qa", "repair"], ["repair", "editorial_timeline"],
            ["editorial_timeline", "final"]
        ]
        payload = {"schema": self.PRODUCTION_GRAPH_SCHEMA, "version": 1,
                   "organization_id": state["organization_id"], "project_id": state["project_id"],
                   "state_digest": state["digest"], "nodes": nodes, "edges": edges,
                   "scenes": [dict(x) for x in (scenes or [])], "shots": [dict(x) for x in (shots or [])],
                   "golden_reference_digest": golden_reference.get("digest") if golden_reference else None,
                   "canonical": True, "prompts_are_derived": True,
                   "governance": {"human_approval_required": True, "external_execution": False, "mcp": False}}
        payload["digest"] = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
        return payload
    def dependency_impact(self, *, organization_id: int, graph: Mapping[str, Any], changed_id: str, changed_kind: str) -> dict[str, Any]:
        if int(organization_id or 0) != int(graph.get("organization_id") or 0):
            raise ValueError("organization_mismatch")
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        target = str(changed_id or "")
        if not target:
            raise ValueError("changed_id_required")
        downstream = set()
        frontier = {target}
        while frontier:
            nxt = set()
            for edge in edges:
                if isinstance(edge, (list, tuple)) and len(edge) >= 2 and str(edge[0]) in frontier and str(edge[1]) not in downstream:
                    downstream.add(str(edge[1])); nxt.add(str(edge[1]))
            frontier = nxt
        affected = [dict(n) for n in nodes if str(n.get("id")) in downstream]
        preserved = [dict(n) for n in nodes if str(n.get("id")) not in downstream and str(n.get("id")) != target]
        return {"schema": "kemet.cinematic.dependency_impact.v1", "version": 1, "organization_id": int(organization_id), "changed": {"id": target, "kind": str(changed_kind)}, "affected": affected, "preserved": preserved, "policy": {"regenerate_affected_only": True, "preserve_unaffected": True, "recompute_downstream_qa": True, "full_project_regeneration": False}, "governance": {"execution_authority": False, "external_execution": False, "human_approval_required": True, "mcp": False}}

    def compile_planning_projection(self, *, state: Mapping[str, Any],
                                    scenes: list[Mapping[str, Any]] | None = None,
                                    shots: list[Mapping[str, Any]] | None = None,
                                    assets: list[Mapping[str, Any]] | None = None,
                                    constraints: list[Mapping[str, Any]] | None = None,
                                    golden_reference: Mapping[str, Any] | None = None,
                                    characters: list[Mapping[str, Any]] | None = None,
                                    world: Mapping[str, Any] | None = None,
                                    story: Mapping[str, Any] | None = None,
                                    production_profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Compile canonical production state into provider-independent planning artifacts.

        This is a planning projection only: it does not execute providers, mutate canonical
        state, publish media, or create a second runtime.
        """
        graph = self.build_graph(state=state, golden_reference=golden_reference,
                                 scenes=scenes, shots=shots)
        from app.services.visual_direction_service import visual_direction_service
        selected_direction = str((state.get("visual_direction") or {}).get("id") or "")
        profile = dict(production_profile or {})
        if not profile and selected_direction:
            profile = visual_direction_service.compile_profile(
                selected_direction, task_type=str((state.get("intent") or {}).get("task_type") or "") or None
            )
        if profile and profile.get("schema") != "kemet.visual.production_profile.v1":
            raise ValueError("production_profile_invalid")
        if profile and profile.get("profile_id") != selected_direction:
            raise ValueError("production_profile_direction_mismatch")
        from app.services.cinematic_production_layer import cinematic_production_layer
        narrative = {
            "schema": "kemet.cinematic.narrative_planning_projection.v1",
            "version": 1,
            "organization_id": int(state["organization_id"]),
            "project_id": str(state["project_id"]),
            "state_digest": str(state["digest"]),
            "story": dict(story or {}),
            "production_profile": profile,
            "characters": [],
            "world": None,
            "stage_order": ["story", "world", "characters", "visual_direction", "shots"],
            "planning_only": True,
            "source_of_truth": "canonical_production_state",
        }
        for character in (characters or []):
            bound = cinematic_production_layer.character_identity(
                organization_id=int(state["organization_id"]), character=character, version=int(character["version"])
            )
            narrative["characters"].append(bound)
        if world:
            narrative["world"] = cinematic_production_layer.world_continuity(
                organization_id=int(state["organization_id"]), world=world, version=int(world["version"])
            )
        narrative["status"] = {
            "story": "bound" if story else "pending",
            "world": "bound" if world else "pending",
            "characters": "bound" if narrative["characters"] else "pending",
            "visual_direction": "selected" if state.get("visual_direction") else "pending",
            "shots": "planned" if shots else "pending",
        }
        narrative["governance"] = {
            "execution_authority": False, "external_execution": False,
            "human_approval_required": True, "mcp": False,
        }
        narrative["digest"] = sha256(json.dumps(
            narrative, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
        ).encode()).hexdigest()
        from app.services.production_intelligence import production_intelligence
        specification = production_intelligence.specification(
            organization_id=int(state["organization_id"]),
            project_id=str(state["project_id"]),
            scenes=list(scenes or []), shots=list(shots or []),
            assets=list(assets or []), constraints=list(constraints or []),
            production_profile=profile,
        )
        return {
            "schema": "kemet.cinematic.planning_projection.v1",
            "version": 1,
            "organization_id": int(state["organization_id"]),
            "project_id": str(state["project_id"]),
            "state_digest": str(state["digest"]),
            "graph": graph,
            "narrative": narrative,
            "specification": specification,
            "source_of_truth": "canonical_production_state",
            "prompts_are_derived": True,
            "planning_only": True,
            "governance": {
                "execution_authority": False,
                "external_execution": False,
                "human_approval_required": True,
                "mcp": False,
            },
        }

    def build_state(self, *, organization_id: int, project_id: str,
                    stage: str, canonical_refs: Mapping[str, Any] | None = None,
                    visual_direction: Mapping[str, Any] | None = None,
                    intent: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        payload = {
            "schema": "kemet.cinematic.production_state.v2",
            "version": 2,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "stage": str(stage),
            "canonical_refs": dict(canonical_refs or {}),
            "intent": dict(intent or {}),
            "visual_direction": dict(visual_direction or {}),
            "source_of_truth": "canonical_production_state",
            "governance": {
                "execution_authority": False,
                "external_execution": False,
                "human_approval_required": True,
                "mcp": False,
            },
        }
        payload["digest"] = sha256(json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
        ).encode()).hexdigest()
        return payload

cinematic_production_os = CinematicProductionOS()
