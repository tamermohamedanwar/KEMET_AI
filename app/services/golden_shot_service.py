from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from app.core.media.qa_gate import media_qa_gate_v1
from app.core.media.render_engine import RenderEngineV1, RenderRequest
from app.services.cinematic_provider_fabric import cinematic_provider_fabric
from app.services.kemet_provenance_lineage_service import kemet_provenance_lineage_service


class GoldenShotService:
    VERSION = "1.1"
    SCHEMA = "kemet.cinematic.golden_shot.v1"
    GENERATION_MODES = ("GENERATIVE_PROVIDER", "KEMET_PROCEDURAL")

    def preflight(self, *, organization_id: int) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "provider": cinematic_provider_fabric.provider_preflight(),
            "render": RenderEngineV1().snapshot(),
            "qa": media_qa_gate_v1.snapshot(),
            "governance": {"human_approval_required": True, "external_execution": False, "mcp": False},
        }

    def build_package(self, *, organization_id: int, production_state: Mapping[str, Any],
                      reference_pack: Mapping[str, Any], character_plates: list[Mapping[str, Any]],
                      world_plates: list[Mapping[str, Any]], shot_plan: Mapping[str, Any],
                      storyboard: Mapping[str, Any], previs: Mapping[str, Any],
                      generation_mode: str = "GENERATIVE_PROVIDER",
                      artifact: Mapping[str, Any] | None = None,
                      qa: Mapping[str, Any] | None = None,
                      provenance: Mapping[str, Any] | None = None,
                      procedural_plan: Mapping[str, Any] | None = None) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        if int(production_state.get("organization_id") or 0) != org:
            raise ValueError("production_state_tenant_mismatch")
        if int(reference_pack.get("organization_id") or 0) != org:
            raise ValueError("reference_pack_tenant_mismatch")
        if not reference_pack.get("digest"):
            raise ValueError("reference_pack_digest_required")
        profile = dict(reference_pack.get("production_profile") or {})
        if profile and profile.get("schema") != "kemet.visual.production_profile.v1":
            raise ValueError("reference_profile_invalid")
        if profile and profile.get("profile_id") != str((production_state.get("visual_direction") or {}).get("id") or profile.get("profile_id")):
            raise ValueError("reference_profile_direction_mismatch")
        generation_mode = str(generation_mode or "").strip().upper()
        if generation_mode not in self.GENERATION_MODES:
            raise ValueError("generation_mode_invalid")
        shots = list(shot_plan.get("shots") or [])
        if generation_mode == "GENERATIVE_PROVIDER" and len(shots) != 1:
            raise ValueError("golden_shot_requires_exactly_one_shot")
        if generation_mode == "KEMET_PROCEDURAL" and not shots:
            raise ValueError("procedural_shot_plan_required")
        shot = dict(shots[0]) if shots else {}
        if generation_mode == "KEMET_PROCEDURAL" and artifact:
            artifact_org = int(artifact.get("organization_id") or 0)
            if artifact_org != org:
                raise ValueError("artifact_tenant_mismatch")
            if len(str(artifact.get("digest") or "")) != 64:
                raise ValueError("artifact_digest_required")
            if str((qa or {}).get("status") or "") != "PASS":
                raise ValueError("artifact_qa_required")
        shot["provider_prompt"] = cinematic_provider_fabric._derive_shot_prompt(shot)
        shot["canonical_shot_digest"] = sha256(json.dumps({k: v for k, v in shot.items() if k != "provider_prompt"}, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")).encode()).hexdigest()
        package = {
            "schema": self.SCHEMA, "version": self.VERSION, "organization_id": org,
            "generation_mode": generation_mode,
            "artifact_kind": "COMMERCIAL" if generation_mode == "KEMET_PROCEDURAL" else "GOLDEN_SHOT",
            "artifact": dict(artifact or {}) if artifact else None,
            "qa": dict(qa or {}) if qa else None,
            "provenance": dict(provenance or {}) if provenance else None,
            "procedural_plan": dict(procedural_plan or {}) if procedural_plan else None,
            "production_state_digest": production_state.get("digest"),
            "reference_pack_digest": reference_pack.get("digest"),
            "production_profile": profile,
            "character_plate_digests": [x.get("digest") for x in character_plates],
            "world_plate_digests": [x.get("digest") for x in world_plates],
            "shot": shot,
            "storyboard_digest": storyboard.get("digest"),
            "previs_digest": previs.get("digest"),
            "canonical": True,
            "prompts_are_derived": True,
            "status": "READY_FOR_APPROVAL",
            "governance": {
                "human_approval_required": True,
                "external_execution": False,
                "mcp": False,
                "network": "disabled" if generation_mode == "KEMET_PROCEDURAL" else "provider_capability_bound",
                "canonical_executor": "kemet",
            },
        }
        package["digest"] = self._digest(package)
        return package

    def execute(self, *, package: Mapping[str, Any], approval: Mapping[str, Any], output_dir: str) -> dict[str, Any]:
        org = int(package.get("organization_id") or 0)
        shot = dict(package.get("shot") or {})
        if approval.get("approved") is not True:
            return {"success": False, "status": "blocked", "error": "human_approval_required", "executed": False}
        if approval.get("organization_id") != org or approval.get("shot_id") != shot.get("shot_id"):
            return {"success": False, "status": "blocked", "error": "approval_binding_mismatch", "executed": False}
        if approval.get("canonical_shot_digest") != shot.get("canonical_shot_digest"):
            return {"success": False, "status": "blocked", "error": "approval_shot_digest_mismatch", "executed": False}
        if str(package.get("generation_mode") or "").upper() == "KEMET_PROCEDURAL":
            authorization = approval.get("execution_authorization")
            if not isinstance(authorization, Mapping):
                return {"success": False, "status": "blocked", "error": "execution_authorization_required", "executed": False}
            procedural_plan = dict(package.get("procedural_plan") or {})
            source_spec = procedural_plan.get("source_spec")
            if not isinstance(source_spec, Mapping) or source_spec.get("type") != "lavfi":
                return {"success": False, "status": "blocked", "error": "procedural_source_required", "executed": False}
            render_request = RenderRequest(org, "", str(Path(output_dir) / "golden_artifact.mp4"),
                                           int(procedural_plan.get("duration_seconds") or 45), source_spec, None, False)
            render_plan = RenderEngineV1().plan(render_request)
            from app.core.execution.authorization import execution_authorization
            from app.core.execution.execution_boundary import execution_boundary
            gate_handoff = authorization.get("gate_handoff")
            if not isinstance(gate_handoff, Mapping):
                return {"success": False, "status": "blocked", "error": "gate_handoff_required", "executed": False}
            execution_key = str(authorization.get("execution_key") or "").strip()
            if not execution_key:
                return {"success": False, "status": "blocked", "error": "execution_key_required", "executed": False}
            render_authorization = dict(authorization)
            boundary = execution_boundary.require(
                plan=dict(render_plan),
                authorization=render_authorization,
                action="media_render",
                subject_id=render_authorization.get("approver_id"),
            )
            if not boundary.get("allowed"):
                return {"success": False, "status": "blocked", "error": str(boundary.get("error") or "execution_boundary_denied"), "executed": False}
            verified = execution_authorization.verify(render_authorization, dict(render_plan), "media_render")
            if not verified.get("authorized"):
                return {"success": False, "status": "blocked", "error": str(verified.get("error") or "execution_authorization_denied"), "executed": False}
            authorization_context = dict(render_authorization)
            authorization_context["_execution_plan"] = dict(render_plan)
            authorization_context["_execution_action"] = "media_render"
            if not execution_authorization.consume(authorization_context, plan=dict(render_plan), action="media_render"):
                return {"success": False, "status": "blocked", "error": "execution_authorization_used", "executed": False}
            render = RenderEngineV1().render(render_plan, approval=True, execution_authorization=render_authorization)
            if not render.get("success"):
                return {"success": False, "status": "render_blocked", "render": render, "executed": False}
            qa = media_qa_gate_v1.inspect(organization_id=org, artifact=render["artifact"])
            if qa.get("status") != "PASS":
                return {"success": False, "status": "qa_blocked", "render": render, "qa": qa, "executed": True}
            return {"success": True, "status": "GOLDEN_SHOT_VERIFIED", "executed": True,
                    "generation_mode": "KEMET_PROCEDURAL", "render": render, "qa": qa,
                    "artifact": render["artifact"], "package_digest": package["digest"]}

        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        authorization = approval.get("execution_authorization")
        if not isinstance(authorization, Mapping):
            return {"success": False, "status": "blocked", "error": "execution_authorization_required", "executed": False}
        gate_handoff = authorization.get("gate_handoff")
        if not isinstance(gate_handoff, Mapping):
            return {"success": False, "status": "blocked", "error": "gate_handoff_required", "executed": False}
        execution_key = str(authorization.get("execution_key") or "").strip()
        if not execution_key:
            return {"success": False, "status": "blocked", "error": "execution_key_required", "executed": False}
        from app.core.execution.authorization import execution_authorization
        from app.core.execution.execution_boundary import execution_boundary
        execution_context = dict(authorization)
        boundary = execution_boundary.require(
            plan=dict(package),
            authorization=execution_context,
            action="media_render",
            subject_id=execution_context.get("approver_id"),
        )
        if not boundary.get("allowed"):
            return {"success": False, "status": "blocked", "error": str(boundary.get("error") or "execution_boundary_denied"), "executed": False}
        verified = execution_authorization.verify(execution_context, dict(package), "media_render")
        if not verified.get("authorized"):
            return {"success": False, "status": "blocked", "error": str(verified.get("error") or "execution_authorization_denied"), "executed": False}
        authorization_context = dict(execution_context)
        authorization_context["_execution_plan"] = dict(package)
        authorization_context["_execution_action"] = "media_render"
        authorization_context["_approved_execution"] = True
        if not execution_authorization.consume(authorization_context, plan=dict(package), action="media_render"):
            return {"success": False, "status": "blocked", "error": "execution_authorization_used", "executed": False}
        provider = cinematic_provider_fabric.execute_approved_video_shot(
            organization_id=org, episode_id=str(package.get("project_id") or "golden-shot"),
            shot=shot, approval=approval, output_path=str(output / "golden_shot_source.mp4"),
        )
        if not provider.get("success"):
            return {"success": False, "status": provider.get("status", "blocked"), "error": provider.get("error"), "provider": provider, "executed": False}
        artifact_uri = str(provider["artifact_uri"])
        render_plan = RenderEngineV1().plan(RenderRequest(org, artifact_uri, str(output / "golden_shot_final.mp4")))
        render = RenderEngineV1().render(render_plan, approval=True, execution_authorization=authorization_context)
        if not render.get("success"):
            return {"success": False, "status": "render_blocked", "provider": provider, "render": render, "executed": True}
        qa = media_qa_gate_v1.inspect(organization_id=org, artifact=render["artifact"])
        if qa.get("status") != "PASS":
            return {"success": False, "status": "qa_blocked", "provider": provider, "render": render, "qa": qa, "executed": True}
        nodes = [
            {"type": "content", "id": "golden-shot", "organization_id": org, "version": 1, "digest": str(package["digest"]), "metadata": {"schema": self.SCHEMA}},
            {"type": "version", "id": str(package.get("reference_pack_digest")), "organization_id": org, "version": 1, "digest": str(package["reference_pack_digest"]), "metadata": {}},
            {"type": "asset", "id": str(render["artifact"]["artifact_id"]), "organization_id": org, "version": 1, "digest": str(render["artifact"]["digest"]), "metadata": {"uri": render["artifact"]["uri"]}},
        ]
        lineage = kemet_provenance_lineage_service.build_chain(organization_id=org, nodes=nodes, trace_id=f"golden-shot:{package['digest'][:16]}")
        return {"success": True, "status": "GOLDEN_SHOT_VERIFIED", "executed": True, "provider": provider, "render": render, "qa": qa, "provenance": lineage, "artifact": render["artifact"], "package_digest": package["digest"]}

    @staticmethod
    def _digest(value: Any) -> str:
        return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")).encode()).hexdigest()


golden_shot_service = GoldenShotService()
