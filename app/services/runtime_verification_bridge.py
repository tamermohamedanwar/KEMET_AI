from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping

from app.services.capability_registry import capability_registry
from app.services.local_acceleration_capability import local_acceleration_capability


class RuntimeVerificationBridge:
    """Canonical evidence bridge for model/runtime/hardware admission."""

    VERSION = "1.0"
    SCHEMA = "kemet.runtime_verification_evidence.v1"

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        import json
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
        return sha256(body).hexdigest()

    @staticmethod
    def _checkpoint(bundle: Mapping[str, Any]) -> dict[str, Any]:
        status = str(bundle.get("checkpoint_status") or "LOCAL_VERIFIED")
        uri = str(bundle.get("checkpoint_uri") or "")
        result: dict[str, Any] = {"status": status, "verified": False, "path": uri or None}
        if status == "NOT_DOWNLOADED":
            return result
        path = Path(uri)
        if not path.is_file():
            result["status"] = "MISSING"
            return result
        digest = sha256(path.read_bytes()).hexdigest()
        result.update({"status": "LOCAL_VERIFIED", "verified": digest == str(bundle.get("checkpoint_digest") or ""), "size": path.stat().st_size, "sha256": digest})
        return result
    @staticmethod
    def _hardware(bundle: Mapping[str, Any], snapshot: Mapping[str, Any]) -> tuple[bool, list[str]]:
        return capability_registry._hardware_matches(bundle.get("hardware_requirements") or {}, snapshot)

    def verify(
        self,
        *,
        bundle: Mapping[str, Any],
        runtime: Mapping[str, Any],
        hardware: Mapping[str, Any] | None = None,
        executor: Callable[[], Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Verify independently gated evidence; execute only when all preconditions are real."""
        model = capability_registry.build_model_bundle(bundle)
        runtime_contract = capability_registry.build_runtime_contract(runtime)
        hardware_snapshot = dict(hardware or local_acceleration_capability.snapshot())
        checkpoint = self._checkpoint(model)
        hardware_ok, hardware_failures = self._hardware(model, hardware_snapshot)
        model_metadata = bool(model.get("model_id") and model.get("model_version") and model.get("model_family") and model.get("modality"))
        license_ok = model.get("commercial_use") is True and model.get("license_evidence", {}).get("verified") is True
        runtime_metadata = all(runtime_contract.get(key) for key in ("runtime_id", "runtime_version", "framework", "backend", "platform"))
        runtime_health = runtime_contract.get("health_status") == "READY" and runtime_contract.get("health_evidence", {}).get("verified") is True
        failures: list[str] = []
        if not model_metadata: failures.append("model_metadata_unverified")
        if not license_ok: failures.append("model_license_unverified")
        if not checkpoint["verified"]: failures.append("checkpoint_not_verified" if checkpoint["status"] != "LOCAL_VERIFIED" else "checkpoint_digest_mismatch")
        if not runtime_metadata: failures.append("runtime_metadata_unverified")
        if not runtime_health: failures.append("runtime_health_unverified")
        if not hardware_ok: failures.extend(hardware_failures)
        execution: dict[str, Any] = {"verified": False, "status": "NOT_ATTEMPTED"}
        benchmark: dict[str, Any] = {"status": "NOT_EXECUTED"}
        if not failures and executor is not None:
            started = perf_counter()
            observed = dict(executor())
            elapsed = perf_counter() - started
            output = Path(str(observed.get("output_path") or ""))
            if not output.is_file() or output.stat().st_size <= 0:
                failures.append("execution_output_invalid")
            else:
                output_digest = sha256(output.read_bytes()).hexdigest()
                if observed.get("output_digest") and observed["output_digest"] != output_digest:
                    failures.append("execution_output_digest_mismatch")
                execution = {"verified": not failures, "status": "VERIFIED" if not failures else "FAILED", "output_path": str(output), "output_size": output.stat().st_size, "output_digest": output_digest, "execution_seconds": round(elapsed, 6), "provenance": dict(observed.get("provenance") or {})}
                benchmark = {"status": "EXECUTED", "execution_seconds": round(elapsed, 6), "output_size": output.stat().st_size, "output_digest": output_digest, "metrics": dict(observed.get("metrics") or {})}
        elif not failures:
            failures.append("execution_not_verified")
        status = "READY" if not failures and execution["verified"] else "BLOCKED"
        evidence = {
            "schema": self.SCHEMA, "version": 1, "model": {"id": model["model_id"], "version": model["model_version"], "digest": model["digest"]},
            "runtime": {"id": runtime_contract["runtime_id"], "version": runtime_contract["runtime_version"], "digest": runtime_contract["digest"]},
            "verification": {"model_metadata_verified": model_metadata, "license_verified": license_ok, "checkpoint_verified": checkpoint["verified"], "runtime_metadata_verified": runtime_metadata, "runtime_health_verified": runtime_health, "hardware_compatibility_verified": hardware_ok, "execution_verified": execution["verified"], "benchmark_verified": benchmark["status"] == "EXECUTED"},
            "checkpoint": checkpoint, "hardware": hardware_snapshot, "execution": execution, "benchmark": benchmark, "status": status, "failures": sorted(set(failures)),
            "governance": {"provider_independent": True, "execution_authority": False, "external_execution": False, "human_approval_required": True, "mcp": False},
        }
        evidence["evidence_digest"] = self._digest(evidence)
        return evidence


runtime_verification_bridge = RuntimeVerificationBridge()
