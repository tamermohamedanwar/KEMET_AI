"""Governed media capability routing over Kemet's existing provider federation."""
from __future__ import annotations
from hashlib import sha256
import json
import os
import shutil
from typing import Any, Iterable
from app.core.federation.capability_federation import capability_federation
from app.core.media.capabilities import MEDIA_CAPABILITIES
from app.core.provider_health import provider_health
from app.core.provider_resilience import provider_resilience
from app.core.provider_usage_telemetry import provider_usage_telemetry

class MediaCapabilityFabric:
    VERSION="1.2"
    def _provider_metadata(self, provider_ids:Iterable[str])->list[dict[str,Any]]:
        health={x["provider_id"]:x for x in provider_health.snapshot()}
        usage={x["provider_id"]:x for x in provider_usage_telemetry.snapshot()}
        resilience={x["provider_id"]:x for x in provider_resilience.status()}
        out=[]
        for provider_id in sorted(set(provider_ids)):
            h=health.get(provider_id,{"healthy":provider_health.is_healthy(provider_id),"last_latency_ms":None})
            u=usage.get(provider_id,{"avg_latency_ms":None,"cost_status":"not_observed","cost_usd_observed":0.0,"requests":0})
            r=resilience.get(provider_id,{"available":provider_resilience.available(provider_id),"last_failure_class":None,"cooldown_seconds":0.0})
            out.append({"provider_id":provider_id,"healthy":bool(h.get("healthy")),"available":bool(r.get("available")),"latency_ms":h.get("last_latency_ms") if h.get("last_latency_ms") is not None else u.get("avg_latency_ms"),"cost_status":u.get("cost_status","not_observed"),"observed_cost_usd":u.get("cost_usd_observed",0.0),"failure_class":r.get("last_failure_class"),"cooldown_seconds":r.get("cooldown_seconds",0.0)})
        return out
    def snapshot(self, *, configured_only:bool=True)->dict[str,Any]:
        snap=capability_federation.snapshot(configured_only=configured_only)
        media=set(MEDIA_CAPABILITIES)
        items=[x for x in snap["capabilities"] if x["capability"] in media]
        providers={p for x in items for p in x["providers"]}
        payload={"version":self.VERSION,"capabilities":items,"providers":self._provider_metadata(providers),"failure_classes":sorted(provider_resilience.FAILURE_CLASSES),"execution_authority":False,"mcp":False}
        raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        payload["fingerprint"]=sha256(raw.encode()).hexdigest()
        payload["local_only_mode"] = self.local_only_mode()
        payload["local_capabilities"] = self.local_snapshot()
        return payload

    @staticmethod
    def local_only_mode() -> bool:
        return os.getenv("KEMET_LOCAL_ONLY_MODE", "").strip().lower() in {"1", "true", "yes", "on"}

    def local_snapshot(self) -> list[dict[str, Any]]:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        piper = shutil.which("piper")
        procedural_ready = bool(ffmpeg and ffprobe)
        statuses: dict[str, str] = {
            "COMPOSITING": "LOCAL_READY" if procedural_ready else "NOT_IMPLEMENTED",
            "RENDERING": "LOCAL_READY" if procedural_ready else "NOT_IMPLEMENTED",
            "VIDEO_GENERATION": "HARDWARE_LIMITED",
            "TEXT_TO_VIDEO": "HARDWARE_LIMITED",
            "PROCEDURAL_VIDEO_GENERATION": "LOCAL_READY" if procedural_ready else "NOT_IMPLEMENTED",
            "VOICE_SYNTHESIS": "BLOCKED" if self._nabra_technical_ready() else "NOT_IMPLEMENTED",
            "TEXT_TO_SPEECH": "BLOCKED" if self._nabra_technical_ready() else "NOT_IMPLEMENTED",
            "IMAGE_GENERATION": "NOT_IMPLEMENTED",
            "IMAGE_TO_VIDEO": "HARDWARE_LIMITED",
            "CHARACTER_ANIMATION": "NOT_IMPLEMENTED",
            "SOUND_GENERATION": "NOT_IMPLEMENTED",
            "MUSIC_GENERATION": "NOT_IMPLEMENTED",
            "UPSCALE": "NOT_IMPLEMENTED",
            "FRAME_INTERPOLATION": "NOT_IMPLEMENTED",
            "TRANSCRIPTION": "LOCAL_READY" if self._transcription_verified() else "NOT_IMPLEMENTED",
            "TRANSLATION": "NOT_IMPLEMENTED",
            "SUBTITLE_GENERATION": "NOT_IMPLEMENTED",
        }
        details = {
            "ffmpeg": ffmpeg,
            "ffprobe": ffprobe,
            "piper": piper,
            "piper_verified": self._piper_verified(),
            "network": "disabled",
            "external_provider_required": False,
            "paid_provider_required": False,
            "execution_authority": False,
            "mcp": False,
        }
        return [{"capability": capability, "status": status, **details} for capability, status in sorted(statuses.items())]

    @staticmethod
    def _nabra_technical_ready() -> bool:
        root=os.getcwd()
        paths=[os.path.join(root,".kemet_runtime","nabra_tts","model.int4.onnx"),os.path.join(root,".kemet_runtime","sherpa_test_full4","sherpa_onnx","lib","libonnxruntime.so"),os.path.join(root,".kemet_runtime","nabra_tts","artifacts","nabra_real_inference_evidence_20260920.json")]
        return all(os.path.isfile(p) and os.path.getsize(p)>0 for p in paths)

    @staticmethod
    def _piper_license_verified() -> bool:
        evidence_path = os.path.join(os.getcwd(), "instance", "production", "self_owned_worker", "kemet_first_self_owned_free_tts_20260920.evidence.json")
        try:
            import json
            with open(evidence_path, encoding="utf-8") as fh:
                evidence = json.load(fh)
            license_data = evidence.get("license") or {}
            return (license_data.get("dataset_license_status") == "VERIFIED"
                    and license_data.get("commercial_use_status") == "VERIFIED"
                    and license_data.get("redistribution_status") == "VERIFIED")
        except (OSError, ValueError, json.JSONDecodeError):
            return False

    @classmethod
    def _piper_verified(cls) -> bool:
        model = os.getenv("KEMET_TTS_MODEL_PATH", "").strip()
        artifact = os.path.join(os.getcwd(), ".kemet_runtime", "piper", "artifacts", "kemet_local_voice_verified_20260920.wav")
        return bool(shutil.which("piper") and os.path.isfile(model) and os.path.isfile(artifact) and cls._piper_license_verified())

    @staticmethod
    def _transcription_verified() -> bool:
        model = os.path.join(os.getcwd(), ".kemet_runtime", "whisper_cpp", "models", "ggml-tiny.bin")
        candidates = [
            os.path.join(os.getcwd(), ".kemet_runtime", "whisper_cpp", "build", "bin", "whisper-cli"),
            os.path.join(os.getcwd(), ".kemet_runtime", "whisper_cpp", "bin", "whisper-cli"),
            shutil.which("whisper-cli") or "",
        ]
        runtime = next((p for p in candidates if p and os.path.isfile(p) and os.access(p, os.X_OK)), "")
        return bool(runtime and os.path.isfile(model) and os.path.getsize(model) >= 70 * 1024 * 1024)

    CANONICAL_STATES = {"READY", "PLANNABLE", "WAITING_FOR_FREE_CAPACITY", "HARDWARE_LIMITED", "NOT_IMPLEMENTED", "BLOCKED"}

    def resolve_truth(self, capability: str, *, verified: set[str] | None = None, local_only: bool | None = None) -> dict[str, Any]:
        """Resolve one capability into the canonical truthful state model."""
        name = str(capability or "").strip().upper()
        if not name or name not in MEDIA_CAPABILITIES:
            return {"capability_id": name, "state": "NOT_IMPLEMENTED", "executable_now": False, "plannable": False, "blocked": False, "blocking_reason": "capability_not_implemented", "provider_independent": True, "execution_authority": False, "evidence_status": "UNAVAILABLE"}
        local = {x["capability"]: x for x in self.local_snapshot()}
        item = local.get(name)
        if item and item.get("status") == "LOCAL_READY":
            return {"capability_id": name, "modality": name.split("_")[0].lower(), "state": "READY", "executable_now": True, "plannable": True, "blocked": False, "blocking_reason": None, "required_runtime": "local", "required_hardware": {}, "required_capacity": "local", "available_capacity": "local", "admission_status": "READY", "governance_status": "READY", "local_available": True, "free_first_allowed": True, "provider_independent": True, "execution_authority": False, "evidence_status": "VERIFIED_LOCAL"}
        if item and item.get("status") == "HARDWARE_LIMITED":
            return {"capability_id": name, "modality": name.split("_")[0].lower(), "state": "HARDWARE_LIMITED", "executable_now": False, "plannable": True, "blocked": True, "blocking_reason": "required_hardware_unavailable", "required_runtime": "local_or_verified_worker", "required_hardware": {"cuda": True}, "required_capacity": "verified_compute", "available_capacity": "none", "admission_status": "HARDWARE_LIMITED", "governance_status": "READY", "local_available": False, "free_first_allowed": True, "provider_independent": True, "execution_authority": False, "evidence_status": "HARDWARE_UNAVAILABLE"}
        if item and item.get("status") == "BLOCKED":
            return {"capability_id": name, "modality": name.split("_")[0].lower(), "state": "BLOCKED", "executable_now": False, "plannable": True, "blocked": True, "blocking_reason": "license_evidence_incomplete", "required_runtime": "verified_runtime", "required_hardware": {}, "required_capacity": "local", "available_capacity": "local", "admission_status": "BLOCKED", "governance_status": "READY", "local_available": False, "free_first_allowed": True, "provider_independent": True, "execution_authority": False, "evidence_status": "LICENSE_INCOMPLETE"}
        if item and item.get("status") == "NOT_IMPLEMENTED":
            return {"capability_id": name, "modality": name.split("_")[0].lower(), "state": "NOT_IMPLEMENTED", "executable_now": False, "plannable": False, "blocked": False, "blocking_reason": "capability_not_implemented", "required_runtime": "none", "required_hardware": {}, "required_capacity": "none", "available_capacity": "none", "admission_status": "NOT_IMPLEMENTED", "governance_status": "READY", "local_available": False, "free_first_allowed": True, "provider_independent": True, "execution_authority": False, "evidence_status": "UNAVAILABLE"}
        if item and item.get("status") in {"LOCAL_POSSIBLE", "WAITING_FOR_FREE_CAPACITY"}:
            return {"capability_id": name, "modality": name.split("_")[0].lower(), "state": "WAITING_FOR_FREE_CAPACITY", "executable_now": False, "plannable": True, "blocked": True, "blocking_reason": "free_capacity_unavailable", "required_runtime": "verified_worker", "required_hardware": {}, "required_capacity": "free_verified", "available_capacity": "none", "admission_status": "WAITING_FOR_FREE_CAPACITY", "governance_status": "READY", "local_available": False, "free_first_allowed": True, "provider_independent": True, "execution_authority": False, "evidence_status": "CAPACITY_UNAVAILABLE"}
        # External provider configuration is not execution evidence for Kemet's
        # self-owned factory. Provider candidates remain internal routing data.
        # A capability becomes READY only through a verified local/owned runtime
        # path handled by the canonical runtime/capacity evidence.
        return {"capability_id": name, "modality": name.split("_")[0].lower(), "state": "PLANNABLE", "executable_now": False, "plannable": True, "blocked": False, "blocking_reason": "no_verified_self_owned_execution_path", "required_runtime": "verified_runtime", "required_hardware": {}, "required_capacity": "verified", "available_capacity": "unknown", "admission_status": "PLAN_ONLY", "governance_status": "READY", "local_available": False, "free_first_allowed": True, "provider_independent": True, "execution_authority": False, "evidence_status": "PLAN_ONLY"}

    def resolve_many(self, required: Iterable[str], *, verified: set[str] | None = None, local_only: bool | None = None) -> dict[str, Any]:
        normalized = []
        for item in required:
            if isinstance(item, dict):
                capability = item.get("capability") or item.get("capability_id")
            else:
                capability = item
            if capability:
                normalized.append(str(capability).strip().upper())
        items = [self.resolve_truth(x, verified=verified, local_only=local_only) for x in normalized]
        blocking = [x for x in items if x["state"] != "READY"]
        state = "READY" if not blocking else ("HARDWARE_LIMITED" if any(x["state"] == "HARDWARE_LIMITED" for x in blocking) else ("WAITING_FOR_FREE_CAPACITY" if any(x["state"] == "WAITING_FOR_FREE_CAPACITY" for x in blocking) else ("NOT_IMPLEMENTED" if any(x["state"] == "NOT_IMPLEMENTED" for x in blocking) else "PLANNABLE")))
        return {"state": state, "executable_now": state == "READY", "requirements": items, "blocking_capabilities": [x["capability_id"] for x in blocking], "provider_independent": True, "execution_authority": False}

    def route(self, required:Iterable[str], *, verified:set[str], preferred:str|None=None, local_only:bool|None=None)->dict[str,Any]:
        required_list=sorted({str(x).strip() for x in required if str(x).strip()})
        unknown=[x for x in required_list if x not in MEDIA_CAPABILITIES]
        if unknown: raise ValueError("unsupported_media_capability")
        if not required_list: raise ValueError("media_capability_required")
        local_mode = self.local_only_mode() if local_only is None else bool(local_only)
        local_by_capability = {x["capability"]: x for x in self.local_snapshot()}
        if local_mode:
            unavailable = [x for x in required_list if local_by_capability.get(x, {}).get("status") != "LOCAL_READY"]
            if unavailable:
                return {
                    "success": False,
                    "status": "blocked",
                    "error": "local_capability_unavailable",
                    "unavailable_capabilities": unavailable,
                    "candidates": [],
                    "provider_metadata": [],
                    "local_only_mode": True,
                    "execution_authority": False,
                    "mcp": False,
                }
            return {
                "success": True,
                "status": "local_ready",
                "candidates": [{"provider_id": "kemet_local", "capability": x, "status": "LOCAL_READY"} for x in required_list],
                "provider_metadata": [],
                "local_only_mode": True,
                "execution_authority": False,
                "mcp": False,
            }
        route=capability_federation.route(required_list,verified=verified,preferred=preferred)
        provider_ids=[x["provider_id"] for x in route.get("candidates",[])]
        route.update({"fabric_version":self.VERSION,"provider_metadata":self._provider_metadata(provider_ids),"failure_classes":sorted(provider_resilience.FAILURE_CLASSES),"execution_authority":False,"mcp":False})
        return route

media_capability_fabric=MediaCapabilityFabric()
