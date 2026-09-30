"""Provider-independent shot routing for Kemet Production OS."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from app.services.provider_capacity_gate import provider_capacity_gate
from app.core.media.capability_fabric import media_capability_fabric
from app.services.free_compute_fabric import FreeComputeFabricV1


class GenerationRouter:
    VERSION = "1.1"
    SCHEMA = "kemet.cinematic.generation_route.v1"

    def route(self, *, organization_id: int, shot: Mapping[str, Any] | None = None, providers: list[Mapping[str, Any]] | None = None, content_intent: str | None = None, production_spec: Mapping[str, Any] | None = None, capability_requirements: list[str] | None = None, free_compute_snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        shot = dict(shot or {})
        providers = list(providers or [])
        if content_intent is not None:
            spec = dict(production_spec or {})
            required_capabilities = list(capability_requirements or spec.get("capability_requirements") or [])
            required_capabilities = [
                (x.get("capability") or x.get("capability_id")) if isinstance(x, Mapping) else x
                for x in required_capabilities
            ]
            required_capabilities = sorted({str(x).strip().upper() for x in required_capabilities if x})
            if not required_capabilities:
                raise ValueError("capability_requirements_required")
            truth = media_capability_fabric.resolve_many(required_capabilities)
            if truth["state"] != "READY" and free_compute_snapshot:
                fabric = FreeComputeFabricV1()
                candidates = [p for p in free_compute_snapshot.get("providers", []) if all(cap in (p.get("capabilities") or []) for cap in required_capabilities) and fabric._capacity_admitted(p)]
                if candidates:
                    selected = sorted(candidates, key=lambda p: (p.get("queue_depth", 10**9), p.get("provider_id", "")))[0]
                    decision = {"schema": self.SCHEMA, "version": 1, "status": "FREE_CAPACITY_READY", "content_intent": content_intent, "required_capabilities": required_capabilities, "capability_resolution": truth, "selection": {"execution_path": "verified_free_worker", "worker_id": selected.get("worker_id"), "provider_id": selected.get("provider_id")}, "ranked_candidates": [{"provider_id": selected.get("provider_id"), "worker_id": selected.get("worker_id"), "cost_classification": fabric.classify_cost(selected), "capabilities": list(selected.get("capabilities") or [])}], "execution": {"automatic": False, "approval_required": True, "external_execution": True}, "governance": {"human_approval_required": True, "execution_authority": False, "external_execution": True, "mcp": False}}
                    decision["digest"] = sha256(json.dumps(decision, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
                    return decision
            if truth["state"] != "READY":
                decision = {"schema": self.SCHEMA, "version": 1, "status": self._decision_for_state(truth["state"]), "content_intent": content_intent, "required_capabilities": required_capabilities, "capability_resolution": truth, "selection": None, "ranked_candidates": [], "execution": {"automatic": False, "approval_required": True, "external_execution": False}, "governance": {"human_approval_required": True, "execution_authority": False, "external_execution": False, "mcp": False}}
                decision["digest"] = sha256(json.dumps(decision, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
                return decision
            decision = {
                "schema": self.SCHEMA, "version": 1, "status": "EXECUTE_NOW",
                "content_intent": content_intent, "required_capabilities": required_capabilities,
                "capability_resolution": truth,
                "selection": {"execution_path": "kemet_local", "capabilities": required_capabilities},
                "ranked_candidates": [{"execution_path": "kemet_local", "capabilities": required_capabilities}],
                "execution": {"automatic": False, "approval_required": True, "external_execution": False},
                "governance": {"human_approval_required": True, "execution_authority": False, "external_execution": False, "mcp": False},
            }
            decision["digest"] = sha256(json.dumps(decision, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
            return decision
        if not shot.get("shot_id") or not shot.get("canonical_shot_digest"):
            raise ValueError("canonical_shot_binding_required")
        candidates = [dict(x) for x in providers if isinstance(x, Mapping) and x.get("provider_id")]
        required_capabilities = ["VIDEO_GENERATION"]
        capacity = provider_capacity_gate.evaluate(providers=candidates, required_capabilities=required_capabilities, shot=shot)
        readiness = {item["provider_id"]: item for item in capacity["providers"]}
        for provider in candidates:
            provider["capacity_gate"] = readiness.get(provider["provider_id"], {"ready": False})
        scored = [(self._score(shot, p), p) for p in candidates if p["capacity_gate"].get("ready") is True]
        scored.sort(key=lambda item: (-item[0], str(item[1].get("provider_id"))))
        ranked = []
        for score, provider in scored:
            ranked.append({
                "provider_id": provider["provider_id"],
                "model": provider.get("model"),
                "score": score,
                "configured": bool(provider.get("configured")),
                "capabilities": list(provider.get("capabilities") or []),
                "capacity": dict(provider.get("capacity") or {}),
                "reasons": self._reasons(shot, provider),
            })
        selected = ranked[0] if ranked else None
        payload = {
            "schema": self.SCHEMA,
            "version": 1,
            "organization_id": int(organization_id),
            "shot_id": str(shot["shot_id"]),
            "canonical_shot_digest": str(shot["canonical_shot_digest"]),
            "selection": selected,
            "ranked_candidates": ranked,
            "capacity_gate": capacity,
            "routing_policy": {
                "shot_level_routing": True,
                "provider_independent": True,
                "continuity_anchor_required_on_provider_switch": True,
                "capacity_gate_required": True,
                "cost_is_a_constraint_not_the_source_of_truth": True,
            },
            "status": "ROUTE_SELECTED" if selected else "ROUTE_BLOCKED",
            "execution": {"automatic": False, "approval_required": True, "external_execution": False},
        }
        payload["digest"] = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
        payload["governance"] = {"human_approval_required": True, "execution_authority": False, "external_execution": False, "mcp": False}
        return payload

    @staticmethod
    def _decision_for_state(state: str) -> str:
        return {"WAITING_FOR_FREE_CAPACITY": "WAIT_FOR_CAPACITY", "HARDWARE_LIMITED": "HARDWARE_BLOCKED", "NOT_IMPLEMENTED": "NOT_SUPPORTED", "BLOCKED": "GOVERNANCE_BLOCKED", "PLANNABLE": "PLAN_ONLY"}.get(state, "PLAN_ONLY")

    @staticmethod
    def _score(shot: Mapping[str, Any], provider: Mapping[str, Any]) -> int:
        caps = {str(x).upper() for x in (provider.get("capabilities") or [])}
        if "VIDEO_GENERATION" not in caps:
            return -1000
        if not provider.get("configured"):
            return -500
        score = 10
        kind = str(shot.get("production_type") or shot.get("shot_type") or "").lower()
        features = {str(x).lower() for x in (provider.get("features") or [])}
        if "animation" in kind and "character_animation" in features:
            score += 30
        if shot.get("reference_images") and "reference_images" in features:
            score += 25
        if shot.get("audio_required") and "native_audio" in features:
            score += 20
        if float(shot.get("duration_seconds") or 0) > 8 and "video_extension" in features:
            score += 15
        if shot.get("high_end_cinematic") and "cinematic" in features:
            score += 20
        return score

    @staticmethod
    def _reasons(shot: Mapping[str, Any], provider: Mapping[str, Any]) -> list[str]:
        reasons = []
        features = {str(x).lower() for x in (provider.get("features") or [])}
        if shot.get("reference_images") and "reference_images" in features:
            reasons.append("reference_support")
        if shot.get("audio_required") and "native_audio" in features:
            reasons.append("native_audio")
        if float(shot.get("duration_seconds") or 0) > 8 and "video_extension" in features:
            reasons.append("extension_support")
        if shot.get("high_end_cinematic") and "cinematic" in features:
            reasons.append("cinematic_capability")
        return reasons


generation_router = GenerationRouter()
