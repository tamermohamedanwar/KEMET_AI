from __future__ import annotations

from typing import Any
from hashlib import sha256
import json

from app.services.mendes.mendes_production_job_store import mendes_production_job_store


class MendesPublicationContractService:
    VERSION = "1.0"

    def validate(self, *, organization_id: int, production_job_id: str, approval: bool | None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            return self._blocked("organization_required")
        if not str(production_job_id or "").strip():
            return self._blocked("production_job_id_required")
        if approval is not True:
            return self._blocked("publication_approval_required")
        try:
            job = mendes_production_job_store.get(int(organization_id), str(production_job_id))
        except ValueError:
            return self._blocked("production_job_not_found")
        if job.get("state") != "VERIFIED":
            return self._blocked("verified_production_required")
        if not job.get("asset_refs"):
            return self._blocked("production_assets_required")
        if not job.get("evidence_refs"):
            return self._blocked("production_evidence_required")
        return {
            "ready": True,
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "production_job_id": str(production_job_id),
            "production_job_digest": job.get("job_digest"),
            "publication_contract_digest": self._digest(int(organization_id), str(production_job_id), str(job.get("job_digest") or "")),
            "approval": True,
            "canonical_runtime_only": True,
            "execution_authority": False,
            "credentials_exposed": False,
        }

    @staticmethod
    def _digest(organization_id: int, production_job_id: str, production_job_digest: str) -> str:
        payload = {"organization_id": organization_id, "production_job_id": production_job_id, "production_job_digest": production_job_digest, "approval": True}
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"ready": False, "status": "blocked", "error": error, "canonical_runtime_only": True, "execution_authority": False, "credentials_exposed": False}


mendes_publication_contract_service = MendesPublicationContractService()
