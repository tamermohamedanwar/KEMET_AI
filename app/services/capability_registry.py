from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from app.automation.playbook_engine import playbook_engine
from app.services.free_compute_fabric import FreeComputeFabricV1
from app.services.local_acceleration_capability import local_acceleration_capability
from app.services.local_media_provider_service import local_media_provider_service
from app.services.piper_tts_service import piper_tts_service
from app.core.media.capability_fabric import media_capability_fabric


class CapabilityRegistry:
    """Read-only production registry composed from governed playbooks and media truth."""

    VERSION = "1.2"
    MODEL_BUNDLE_SCHEMA = "kemet.model_bundle.v1"
    RUNTIME_CONTRACT_SCHEMA = "kemet.runtime_contract.v1"
    LIFECYCLE = {"draft", "active", "deprecated", "disabled"}
    LIFECYCLE_DEFAULT = "active"

    def __init__(self) -> None:
        self._overrides = {
            "refund_request": {"lifecycle": "active", "tags": ["finance", "approval"]},
            "business_insights": {"lifecycle": "active", "tags": ["insights", "read_only"]},
        }

    def _definition(self, action: str) -> dict[str, Any] | None:
        definition = playbook_engine.get_definition(action)
        if not definition:
            return None
        meta = self._overrides.get(action, {})
        item = deepcopy(definition)
        item.update(meta)
        item.setdefault("lifecycle", self.LIFECYCLE_DEFAULT)
        item.setdefault("tags", [item.get("domain", "general")])
        item["capability_id"] = f"kemet.{action}"
        item["registry_version"] = self.VERSION
        item["expected_outcomes"] = [item.get("outcome", "")] if item.get("outcome") else []
        item["metrics"] = [
            {"key": "execution_success_rate", "unit": "percent", "source": "automation"},
            {"key": "business_outcome_status", "unit": "status", "source": "outcome"},
        ]
        item["governance"] = {"advisory": True, "fail_closed": True,
                               "requires_approval": action == "refund_request",
                               "external_execution": False, "database_mutation": False}
        item["execution_profile"] = {"mode": "governed_sequential", "checkpointing": True,
                                      "resumable": True, "retry_policy": {"max_attempts": 2, "backoff_seconds": 1}}
        return item

    def catalog(self, lifecycle: str | None = None) -> list[dict[str, Any]]:
        if lifecycle is not None and lifecycle not in self.LIFECYCLE:
            raise ValueError("Invalid capability lifecycle.")
        items = [self._definition(action) for action in playbook_engine.PLAYBOOK_CATALOG]
        return [item for item in items if item and (lifecycle is None or item["lifecycle"] == lifecycle)]

    def get(self, capability_id: str) -> dict[str, Any] | None:
        if not capability_id.startswith("kemet."):
            return None
        return self._definition(capability_id.removeprefix("kemet."))

    def media_catalog(self, organization_id: int | None = None) -> list[dict[str, Any]]:
        """Canonical read-only media capability truth; execution candidates remain internal."""
        capability_names = (
            "TEXT_GENERATION", "IMAGE_GENERATION", "VIDEO_GENERATION", "IMAGE_TO_VIDEO",
            "TEXT_TO_VIDEO", "CHARACTER_ANIMATION", "VOICE_SYNTHESIS", "TEXT_TO_SPEECH",
            "SOUND_GENERATION", "MUSIC_GENERATION", "TRANSCRIPTION", "TRANSLATION",
            "SUBTITLE_GENERATION", "VIDEO_UNDERSTANDING", "IMAGE_UNDERSTANDING",
            "COMPOSITING", "RENDERING", "ANIMATION", "MOTION_GRAPHICS",
        )
        records = []
        kind_map = {
            "TEXT_GENERATION": "text", "IMAGE_GENERATION": "image",
            "VIDEO_GENERATION": "video", "IMAGE_TO_VIDEO": "video",
            "TEXT_TO_VIDEO": "video", "CHARACTER_ANIMATION": "animation",
            "VOICE_SYNTHESIS": "voice", "TEXT_TO_SPEECH": "voice",
            "SOUND_GENERATION": "audio", "MUSIC_GENERATION": "audio",
            "TRANSCRIPTION": "language", "TRANSLATION": "language",
            "SUBTITLE_GENERATION": "language", "VIDEO_UNDERSTANDING": "video",
            "IMAGE_UNDERSTANDING": "image", "COMPOSITING": "finishing",
            "RENDERING": "finishing", "ANIMATION": "animation",
            "MOTION_GRAPHICS": "motion_graphics",
        }
        for name in capability_names:
            record = media_capability_fabric.resolve_truth(name)
            record["kind"] = kind_map.get(name, name.lower())
            record["status"] = record["state"]
            records.append(record)
        return records

    def self_owned_catalog(self, organization_id: int | None = None) -> dict[str, Any]:
        """Canonical read-only inventory of Kemet-owned/local capabilities, separate from provider capacity."""
        media = self.media_catalog(organization_id)
        acceleration = local_acceleration_capability.snapshot()
        local_media = local_media_provider_service.snapshot(organization_id)
        return {
            "schema": "kemet.self_owned_capability_catalog.v1",
            "version": "1.0",
            "ownership": "KEMET_LOCAL_RUNTIME",
            "compute": {
                "state": "LOCAL_READY" if acceleration["cuda"]["available"] else "CPU_ONLY",
                "acceleration": acceleration,
            },
            "media": media,
            "local_media": local_media,
            "governance": {
                "read_only": True,
                "execution_authority": False,
                "external_execution": False,
                "provider_dependency": False,
                "license_review_required": True,
            },
        }

    @staticmethod
    def _canonical_digest(payload: Mapping[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
        return sha256(body).hexdigest()

    @staticmethod
    def _hardware_matches(requirements: Mapping[str, Any], hardware: Mapping[str, Any]) -> tuple[bool, list[str]]:
        failures: list[str] = []
        req_vram = float(requirements.get("vram_gb", 0) or 0)
        actual_vram = max([float(x) for x in (hardware.get("vram_gb") or [])] or [0.0])
        if req_vram > actual_vram:
            failures.append("vram_insufficient")
        req_ram = float(requirements.get("ram_gb", 0) or 0)
        actual_ram = float(hardware.get("ram_gb") or 0)
        if req_ram > actual_ram:
            failures.append("ram_insufficient")
        req_disk = float(requirements.get("disk_free_gb", 0) or 0)
        actual_disk = float(hardware.get("disk_free_gb") or 0)
        if req_disk > actual_disk:
            failures.append("disk_insufficient")
        if requirements.get("cuda_required") is True and not bool((hardware.get("cuda") or {}).get("available")):
            failures.append("cuda_unavailable")
        required_arch = str(requirements.get("architecture") or "").strip().lower()
        actual_arch = str(hardware.get("architecture") or "").strip().lower()
        if required_arch and actual_arch and required_arch != actual_arch:
            failures.append("architecture_mismatch")
        return not failures, failures

    def build_model_bundle(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        """Normalize a provider-independent self-owned model contract without granting readiness."""
        required = ("model_id", "model_version", "model_family", "modality", "checkpoint_uri")
        if any(not str(bundle.get(key) or "").strip() for key in required):
            raise ValueError("model_bundle_identity_required")
        checkpoint_status = str(bundle.get("checkpoint_status") or "LOCAL_VERIFIED")
        if checkpoint_status == "LOCAL_VERIFIED" and not str(bundle.get("checkpoint_digest") or "").strip():
            raise ValueError("checkpoint_digest_required_for_local_verified_model")
        payload = dict(bundle)
        payload["schema"] = self.MODEL_BUNDLE_SCHEMA
        payload["version"] = 1
        payload["provider_independent"] = True
        payload["provider_id"] = None
        payload["execution_authority"] = False
        payload["external_execution"] = False
        payload["commercial_use"] = bool(payload.get("commercial_use") is True)
        payload["license_evidence"] = dict(payload.get("license_evidence") or {})
        payload["hardware_requirements"] = dict(payload.get("hardware_requirements") or {})
        payload["benchmark_evidence"] = list(payload.get("benchmark_evidence") or [])
        payload["checkpoint_status"] = checkpoint_status
        payload["readiness"] = "DISCOVERED"
        unsigned = dict(payload)
        unsigned.pop("digest", None)
        payload["digest"] = self._canonical_digest(unsigned)
        return payload

    def build_runtime_contract(self, runtime: Mapping[str, Any]) -> dict[str, Any]:
        """Normalize an independently verifiable runtime contract."""
        required = ("runtime_id", "runtime_version", "framework", "backend", "platform")
        if any(not str(runtime.get(key) or "").strip() for key in required):
            raise ValueError("runtime_contract_identity_required")
        payload = dict(runtime)
        payload["schema"] = self.RUNTIME_CONTRACT_SCHEMA
        payload["version"] = 1
        payload["health_status"] = str(payload.get("health_status") or "UNKNOWN")
        payload["health_evidence"] = dict(payload.get("health_evidence") or {})
        payload["commercial_use"] = bool(payload.get("commercial_use") is True)
        payload["license_evidence"] = dict(payload.get("license_evidence") or {})
        payload["execution_authority"] = False
        payload["external_execution"] = False
        unsigned = dict(payload)
        unsigned.pop("digest", None)
        payload["digest"] = self._canonical_digest(unsigned)
        return payload

    def discover_model_candidate(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        bundle = dict(candidate)
        bundle.setdefault("checkpoint_status", "NOT_DOWNLOADED")
        model = self.build_model_bundle(bundle)
        model["readiness"] = "DISCOVERED"
        model["verification"] = {"model_metadata_verified": True, "license_verified": model["license_evidence"].get("verified") is True, "checkpoint_verified": model["checkpoint_status"] == "LOCAL_VERIFIED", "execution_verified": False, "benchmark_status": "NOT_EXECUTED"}
        return {"schema": "kemet.model_candidate.v1", "status": "DISCOVERED", "model": model, "provider_independent": True, "next_admission": "BLOCKED_UNTIL_CHECKPOINT_AND_RUNTIME_EVIDENCE"}

    def admit_model_runtime(self, *, bundle: Mapping[str, Any], runtime: Mapping[str, Any], hardware: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Fail-closed admission: integrity, license, hardware and real runtime health are all required."""
        model = self.build_model_bundle(bundle)
        runtime_contract = self.build_runtime_contract(runtime)
        hardware_snapshot = dict(hardware or local_acceleration_capability.snapshot())
        failures: list[str] = []
        checkpoint = Path(str(model["checkpoint_uri"]))
        if model.get("checkpoint_status") == "NOT_DOWNLOADED":
            failures.append("checkpoint_not_downloaded")
        elif not checkpoint.is_file():
            failures.append("checkpoint_missing")
        else:
            observed = sha256(checkpoint.read_bytes()).hexdigest()
            if observed != str(model["checkpoint_digest"]):
                failures.append("checkpoint_digest_mismatch")
        license_evidence = model["license_evidence"]
        if model["commercial_use"] is not True or license_evidence.get("verified") is not True:
            failures.append("model_commercial_license_unverified")
        runtime_license = runtime_contract["license_evidence"]
        if runtime_contract["commercial_use"] is not True or runtime_license.get("verified") is not True:
            failures.append("runtime_commercial_license_unverified")
        if runtime_contract["health_status"] != "READY" or runtime_contract["health_evidence"].get("verified") is not True:
            failures.append("runtime_health_unverified")
        hardware_ok, hardware_failures = self._hardware_matches(model["hardware_requirements"], hardware_snapshot)
        if not hardware_ok:
            failures.extend(hardware_failures)
        benchmark = model["benchmark_evidence"]
        if not benchmark:
            failures.append("benchmark_evidence_missing")
        status = "READY" if not failures else "BLOCKED"
        return {
            "schema": "kemet.model_runtime_admission.v1",
            "status": status,
            "model": model,
            "runtime": runtime_contract,
            "hardware": hardware_snapshot,
            "failures": sorted(set(failures)),
            "governance": {
                "provider_independent": True,
                "execution_authority": False,
                "external_execution": False,
                "human_approval_required": True,
                "mcp": False,
            },
        }

    def plan(self, capability_id: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        definition = self.get(capability_id)
        if not definition or definition["lifecycle"] != "active":
            raise ValueError("Capability is unavailable.")
        action = definition["action"]
        plan = {"action": action, "intent": definition["name"], "parameters": parameters or {}, "confidence": 1.0}
        playbook = playbook_engine.build(plan)
        return {"success": True, "status": "planned", "capability": definition, "playbook": playbook}


capability_registry = CapabilityRegistry()
