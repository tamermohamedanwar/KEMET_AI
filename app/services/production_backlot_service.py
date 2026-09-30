from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from app.services.production_studio_service import production_studio_service
from app.services.social_connection_hub import social_connection_hub
from app.services.tool_intelligence_registry import tool_intelligence_registry


class ProductionBacklotService:
    VERSION = "1.0"

    def snapshot(self, organization_id: int, title: str = "Hikayat Mendes", job: dict[str, Any] | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        studio = production_studio_service.plan(
            organization_id=int(organization_id),
            title=title,
            language="ar-EG",
            duration_seconds=90,
            platforms=["youtube", "tiktok", "instagram", "facebook", "telegram", "whatsapp"],
        )
        connections = social_connection_hub.snapshot(int(organization_id))
        stages = []
        for stage in studio["stages"]:
            stages.append({
                **stage,
                "state": "planned",
                "progress": 0,
                "cost": {"estimated": None, "currency": "USD"},
                "asset_count": 0,
                "evidence": None,
            })
        payload = {
            "version": self.VERSION,
            "mode": "production_backlot",
            "organization_id": int(organization_id),
            "project": {
                "title": str(title).strip()[:200],
                "world": "Mendes World",
                "series": "Hikayat Mendes",
            },
            "pipeline": {
                "state": str((job or {}).get("state") or "PLANNED").lower(),
                "stages": stages,
                "quality_gates": ["creative", "rights", "budget", "distribution"],
            },
            "tools": tool_intelligence_registry.snapshot(int(organization_id)),
            "distribution": connections,
            "production_job": self._job_view(job, int(organization_id)),
            "economics": {
                "production_cost_estimate": None,
                "distribution_cost_estimate": None,
                "verified_revenue": None,
                "qualified_views": None,
                "revenue_per_1000_qualified_views": None,
            },
            "governance": {
                "read_only": True,
                "human_approval_required": True,
                "canonical_runtime_only": True,
                "auto_publish": False,
                "credentials_exposed": False,
            },
        }
        digest = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        payload["backlot_digest"] = digest
        return payload

    @staticmethod
    def _job_view(job: dict[str, Any] | None, organization_id: int) -> dict[str, Any]:
        if not job:
            return {
                "status": "not_created",
                "state": "PLANNED",
                "organization_id": organization_id,
                "job_digest": None,
                "idempotency_key": None,
                "asset_count": 0,
                "evidence_count": 0,
                "governed": True,
            }
        if int(job.get("organization_id") or 0) != organization_id:
            raise ValueError("production_job_tenant_mismatch")
        return {
            "status": "bound",
            "state": job.get("state"),
            "organization_id": organization_id,
            "job_digest": job.get("job_digest"),
            "idempotency_key": job.get("idempotency_key"),
            "episode_package_digest": job.get("episode_package_digest"),
            "script_digest": job.get("script_digest"),
            "voice_contract_digest": job.get("voice_contract_digest"),
            "asset_count": len(job.get("asset_refs") or []),
            "evidence_count": len(job.get("evidence_refs") or []),
            "governed": bool((job.get("governance") or {}).get("canonical_runtime_only")),
        }



production_backlot_service = ProductionBacklotService()
