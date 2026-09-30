from __future__ import annotations

import json
from hashlib import sha256
from uuid import uuid4
from typing import Any

from app import db
from app.models.mendes_production_job import MendesProductionJobRecord, MendesProductionJobTransition
from app.services.mendes.mendes_production_job_service import mendes_production_job_service


class MendesProductionJobStore:
    VERSION = "1.1"

    @staticmethod
    def _digest(value: Any) -> str:
        return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()

    @staticmethod
    def _decode(record: MendesProductionJobRecord) -> dict[str, Any]:
        return {
            "job_id": record.job_id,
            "organization_id": record.organization_id,
            "idempotency_key": record.idempotency_key,
            "workflow_purpose": (
                "readiness" if str(record.idempotency_key).startswith("mendes:readiness:")
                else "production" if str(record.idempotency_key).startswith("mendes:production:")
                else "production"
            ),
            "state": record.state,
            "episode_package_digest": record.episode_package_digest,
            "script_digest": record.script_digest,
            "voice_contract_digest": record.voice_contract_digest,
            "quality_gates": json.loads(record.quality_gates_json),
            "approval_state": record.approval_state,
            "asset_refs": json.loads(record.asset_refs_json),
            "evidence_refs": json.loads(record.evidence_refs_json),
            "job_digest": record.job_digest,
            "governance": {"canonical_runtime_only": True, "execution_authority": False, "human_approval_required": True},
        }

    def create(self, organization_id: int, episode_package: dict[str, Any], voice_contract: dict[str, Any], quality_gates: list[str], **kwargs: Any) -> dict[str, Any]:
        candidate = mendes_production_job_service.create(organization_id, episode_package, voice_contract, quality_gates, **kwargs)
        raw_idempotency_key = str(kwargs.get("idempotency_key") or "").strip()
        legacy_existing = MendesProductionJobRecord.query.filter_by(organization_id=int(organization_id), idempotency_key=raw_idempotency_key).first() if raw_idempotency_key and str(kwargs.get("workflow_purpose") or "production") == "production" else None
        if legacy_existing:
            candidate["idempotency_key"] = legacy_existing.idempotency_key
        existing = MendesProductionJobRecord.query.filter_by(organization_id=int(organization_id), idempotency_key=candidate["idempotency_key"]).first()
        if existing:
            incoming = dict(candidate)
            incoming["organization_id"] = int(organization_id)
            mendes_production_job_service.replay(self._decode(existing), incoming)
            return {**self._decode(existing), "replayed": True}
        job_id = f"mendes-job-{uuid4().hex}"
        record = MendesProductionJobRecord(
            organization_id=int(organization_id), job_id=job_id, idempotency_key=candidate["idempotency_key"],
            state="PLANNED", episode_package_digest=candidate["episode_package_digest"], script_digest=candidate["script_digest"],
            voice_contract_digest=candidate["voice_contract_digest"], quality_gates_json=json.dumps(candidate["quality_gates"], sort_keys=True),
            approval_state=candidate["approval_state"], asset_refs_json=json.dumps(candidate["asset_refs"], sort_keys=True, default=str),
            evidence_refs_json=json.dumps(candidate["evidence_refs"], sort_keys=True, default=str), job_digest=candidate["job_digest"],
        )
        db.session.add(record)
        db.session.commit()
        return {**self._decode(record), "replayed": False}

    def transition(self, organization_id: int, job_id: str, target_state: str, approval: bool | None = None, evidence: dict[str, Any] | None = None, asset_refs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        record = MendesProductionJobRecord.query.filter_by(organization_id=int(organization_id), job_id=str(job_id)).first()
        if not record:
            raise ValueError("production_job_not_found")
        current = self._decode(record)
        updated = mendes_production_job_service.transition(current, target_state, approval=approval, evidence=evidence)
        evidence_digest = self._digest(evidence) if evidence else None
        transition_digest = self._digest({"job_id": job_id, "from": record.state, "to": target_state, "evidence_digest": evidence_digest})
        record.state = updated["state"]
        if asset_refs is not None:
            updated["asset_refs"] = list(asset_refs)
            record.asset_refs_json = json.dumps(updated["asset_refs"], sort_keys=True, default=str)
        record.evidence_refs_json = json.dumps(updated.get("evidence_refs") or [], sort_keys=True, default=str)
        record.job_digest = updated["job_digest"]
        db.session.add(MendesProductionJobTransition(
            organization_id=int(organization_id), job_id=str(job_id), from_state=current["state"], to_state=target_state,
            approval_granted=approval is True, transition_digest=transition_digest, evidence_digest=evidence_digest,
            metadata_json=json.dumps({"version": self.VERSION, "canonical_runtime_only": True}, sort_keys=True),
        ))
        db.session.commit()
        return self._decode(record)

    def set_asset_refs(self, organization_id: int, job_id: str, asset_refs: list[dict[str, Any]]) -> dict[str, Any]:
        record = MendesProductionJobRecord.query.filter_by(organization_id=int(organization_id), job_id=str(job_id)).first()
        if not record:
            raise ValueError("production_job_not_found")
        if not isinstance(asset_refs, list) or not asset_refs:
            raise ValueError("asset_reference_required")
        record.asset_refs_json = json.dumps(asset_refs, sort_keys=True, default=str)
        record.job_digest = mendes_production_job_service._digest({k: v for k, v in self._decode(record).items() if k != "job_digest"})
        db.session.commit()
        return self._decode(record)

    def get(self, organization_id: int, job_id: str) -> dict[str, Any]:
        record = MendesProductionJobRecord.query.filter_by(organization_id=int(organization_id), job_id=str(job_id)).first()
        if not record:
            raise ValueError("production_job_not_found")
        return self._decode(record)


mendes_production_job_store = MendesProductionJobStore()
