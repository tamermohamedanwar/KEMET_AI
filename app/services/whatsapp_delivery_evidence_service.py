from __future__ import annotations

from typing import Any, Mapping

from app.services.whatsapp_cloud_api_service import whatsapp_cloud_api_service
from app.core.execution_evidence import execution_evidence
from app.models.execution_evidence import ExecutionEvidence


class WhatsAppDeliveryEvidenceService:
    VERSION = "1.0"
    STATUSES = ("sent", "delivered", "read", "failed")

    def normalize(self, *, organization_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        result = whatsapp_cloud_api_service.delivery_event(
            organization_id=int(organization_id), payload=payload
        )
        result["evidence"] = {
            "message_id": result["message_id"],
            "status": result["status"],
            "provider": result["provider"],
            "recorded": True,
        }
        return result

    def event_key(self, *, organization_id: int, message_id: str, status: str) -> str:
        return f"whatsapp:{int(organization_id)}:delivery:{message_id}:{status}"

    def correlate_execution(self, *, organization_id: int, message_id: str) -> dict[str, Any] | None:
        token = str(message_id or "").strip()
        if not organization_id or not token:
            return None
        row = (ExecutionEvidence.query
               .filter(ExecutionEvidence.organization_id == int(organization_id))
               .filter(ExecutionEvidence.receipt_json.like(f"%{token}%"))
               .order_by(ExecutionEvidence.id.desc())
               .first())
        if row is None:
            return None
        return {"execution_key": row.execution_key, "job_id": row.job_id, "evidence_key": row.evidence_key}

    def record_delivery(self, *, organization_id: int, message_id: str, status: str,
                        metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        correlation = self.correlate_execution(organization_id=organization_id, message_id=message_id)
        execution_key = correlation.get("execution_key") if correlation else None
        result = {
            "execution_key": execution_key,
            "job_id": correlation.get("job_id") if correlation else None,
            "correlation": correlation,
            "delivery_status": status,
            "message_id": message_id,
            "provider": "meta_whatsapp_cloud",
            "evidence_stage": "channel.delivery",
        }
        if execution_key:
            evidence_key = self.event_key(organization_id=organization_id, message_id=message_id, status=status)
            execution_evidence.record(
                organization_id=int(organization_id), execution_key=execution_key,
                job_id=correlation.get("job_id"), stage="channel.delivery", status=status,
                evidence_key=evidence_key, receipt={"provider": "meta_whatsapp_cloud",
                "message_id": message_id, "delivery_status": status, "metadata": dict(metadata or {})},
            )
        return result


whatsapp_delivery_evidence_service = WhatsAppDeliveryEvidenceService()
