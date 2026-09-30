from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


class MendesProductionJobService:
    VERSION = "1.1"
    WORKFLOW_PURPOSES = ("production", "readiness")
    STATES = ("PLANNED", "APPROVED", "PRODUCING", "PRODUCED", "VERIFIED", "BLOCKED", "FAILED")
    TERMINAL = {"VERIFIED", "BLOCKED", "FAILED"}
    TRANSITIONS = {
        "PLANNED": {"APPROVED", "BLOCKED"},
        "APPROVED": {"PRODUCING", "BLOCKED"},
        "PRODUCING": {"PRODUCED", "FAILED"},
        "PRODUCED": {"VERIFIED", "FAILED"},
        "VERIFIED": set(),
        "BLOCKED": set(),
        "FAILED": set(),
    }

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return sha256(raw.encode()).hexdigest()

    def create(
        self,
        organization_id: int,
        episode_package: dict[str, Any],
        voice_contract: dict[str, Any],
        quality_gates: list[str],
        approval_state: str = "pending",
        asset_refs: list[dict[str, Any]] | None = None,
        evidence_refs: list[dict[str, Any]] | None = None,
        idempotency_key: str | None = None,
        workflow_purpose: str = "production",
    ) -> dict[str, Any]:
        org = int(organization_id or 0)
        workflow = str(workflow_purpose or "production").strip().lower()
        if workflow not in self.WORKFLOW_PURPOSES:
            raise ValueError("invalid_workflow_purpose")
        if org <= 0:
            raise ValueError("organization_required")
        if int(episode_package.get("organization_id") or 0) != org:
            raise ValueError("episode_package_tenant_mismatch")
        if int(voice_contract.get("organization_id") or 0) != org:
            raise ValueError("voice_contract_tenant_mismatch")
        package_digest = str(episode_package.get("package_digest") or "")
        script_digest = str(episode_package.get("script_digest") or voice_contract.get("script_digest") or "")
        voice_digest = str(voice_contract.get("contract_digest") or "")
        if not package_digest:
            raise ValueError("episode_package_digest_required")
        if not script_digest:
            raise ValueError("script_digest_required")
        if not voice_digest:
            raise ValueError("voice_contract_digest_required")
        if approval_state not in {"pending", "approved"}:
            raise ValueError("invalid_approval_state")
        episode = episode_package.get("episode") or {}
        episode_identity = {"episode_id": episode.get("episode_id"), "season": episode.get("season"), "episode": episode.get("episode")}
        operation_key = self._digest({"organization_id": org, "workflow_purpose": workflow, "episode_identity": episode_identity, "episode_package_digest": package_digest, "script_digest": script_digest, "voice_contract_digest": voice_digest, "requested_idempotency_key": str(idempotency_key or "")})
        if not isinstance(quality_gates, list) or not quality_gates:
            raise ValueError("quality_gates_required")
        payload = {
            "version": self.VERSION,
            "organization_id": org,
            "episode_package_digest": package_digest,
            "script_digest": script_digest,
            "workflow_purpose": workflow,
            "episode_identity": episode_identity,
            "voice_contract_digest": voice_digest,
            "quality_gates": sorted({str(x) for x in quality_gates if str(x).strip()}),
            "approval_state": approval_state,
            "asset_refs": asset_refs or [],
            "evidence_refs": evidence_refs or [],
            "idempotency_key": f"mendes:{workflow}:{operation_key}",
            "state": "PLANNED",
        }
        if not payload["quality_gates"]:
            raise ValueError("quality_gates_required")
        payload["job_id"] = f"mendes:{workflow}:{operation_key[:24]}"
        payload["job_digest"] = self._digest(payload)
        payload["governance"] = {
            "read_only_contract": True,
            "execution_authority": False,
            "external_execution": False,
            "database_mutation": False,
            "human_approval_required": True,
            "canonical_runtime_only": True,
        }
        return payload

    def transition(self, job: dict[str, Any], target_state: str, approval: bool | None = None, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        current = str(job.get("state") or "")
        target = str(target_state or "")
        if current not in self.STATES or target not in self.STATES:
            raise ValueError("invalid_state")
        if target not in self.TRANSITIONS[current]:
            raise ValueError("illegal_state_transition")
        if target in {"APPROVED", "PRODUCING"} and approval is not True:
            raise ValueError("approval_required")
        if target in {"VERIFIED"} and not evidence:
            raise ValueError("verification_evidence_required")
        if target == "PRODUCED" and not job.get("asset_refs"):
            raise ValueError("asset_reference_required")
        updated = dict(job)
        updated["state"] = target
        if evidence is not None:
            updated["evidence_refs"] = list(updated.get("evidence_refs") or []) + [evidence]
        updated["job_digest"] = self._digest({k: v for k, v in updated.items() if k != "job_digest"})
        return updated

    def replay(self, existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        if int(existing.get("organization_id") or 0) != int(incoming.get("organization_id") or 0):
            raise ValueError("replay_tenant_mismatch")
        if existing.get("idempotency_key") != incoming.get("idempotency_key"):
            raise ValueError("idempotency_key_mismatch")
        if existing.get("workflow_purpose") and incoming.get("workflow_purpose") and existing.get("workflow_purpose") != incoming.get("workflow_purpose"):
            raise ValueError("workflow_purpose_mismatch")
        if existing.get("episode_identity") and incoming.get("episode_identity") and existing.get("episode_identity") != incoming.get("episode_identity"):
            raise ValueError("episode_identity_mismatch")
        comparable = ("episode_package_digest", "script_digest", "voice_contract_digest", "quality_gates")
        for key in comparable:
            if existing.get(key) != incoming.get(key):
                raise ValueError("replay_payload_mismatch")
        return {"replayed": True, "state": existing.get("state"), "job_digest": existing.get("job_digest")}


mendes_production_job_service = MendesProductionJobService()
