from __future__ import annotations

from typing import Any

from app.core.execution_evidence import execution_evidence


class PublicationEvidenceService:
    VERSION = "1.0"

    def verify(self, *, organization_id: int, execution_key: str, channel: str) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        key = str(execution_key or "").strip()
        clean_channel = str(channel or "").strip().lower()
        if not key or clean_channel not in {"facebook", "instagram", "telegram"}:
            raise ValueError("publication_binding_required")
        rows = execution_evidence.history(organization_id=int(organization_id), execution_key=key)
        matches = [
            row for row in rows
            if row.get("stage") == f"channel.{clean_channel}.publish"
            and row.get("status") == "published"
        ]
        verified = []
        for row in matches:
            receipt = row.get("receipt") or {}
            publication_id = str(receipt.get("publication_id") or "").strip()
            provider = str(receipt.get("provider") or clean_channel).strip()
            if not publication_id:
                continue
            verified.append({
                "evidence_id": row.get("id"),
                "evidence_key": row.get("evidence_key"),
                "execution_key": key,
                "channel": clean_channel,
                "provider": provider,
                "publication_id": publication_id,
                "status": "published",
                "receipt_verified": True,
                "metrics_verified": False,
                "revenue_verified": False,
            })
        return {
            "success": True,
            "status": "publication_verified" if verified else "publication_evidence_missing",
            "verified": bool(verified),
            "organization_id": int(organization_id),
            "execution_key": key,
            "channel": clean_channel,
            "records": verified,
            "governance": {
                "read_only": True,
                "external_execution": False,
                "financial_action": False,
                "causal_claim": False,
                "roi_claim": False,
            },
        }


publication_evidence_service = PublicationEvidenceService()
