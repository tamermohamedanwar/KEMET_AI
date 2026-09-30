from __future__ import annotations

from typing import Any, Iterable

from app import db
from app.models.demo_lead import DemoLead
from app.services.lead_intelligence_service import lead_intelligence_service


class LeadDiscoveryService:
    """Tenant-bound ingestion boundary for permitted lead sources."""

    VERSION = "1.0"
    ALLOWED_SOURCES = frozenset({
        "website",
        "referral",
        "demo",
        "contact_form",
        "google_sheets",
        "salla",
        "crm",
    })

    @classmethod
    def validate_source(cls, source: str) -> str:
        normalized = lead_intelligence_service._clean(source).lower()
        if normalized not in cls.ALLOWED_SOURCES:
            raise ValueError("lead_source_not_allowed")
        return normalized

    @classmethod
    def _dedup_key(cls, tenant_id: int, record: dict[str, Any]) -> str:
        payload = {
            "tenant_id": int(tenant_id),
            "email": lead_intelligence_service.normalize_email(record.get("email")),
            "phone": lead_intelligence_service.normalize_phone(record.get("phone")),
            "company": lead_intelligence_service.normalize_company(record.get("company_name")),
        }
        return lead_intelligence_service._digest(payload)

    @classmethod
    def ingest_one(cls, *, tenant_id: int, record: dict[str, Any], source: str) -> dict[str, Any]:
        if int(tenant_id) <= 0:
            raise ValueError("tenant_id_required")
        source = cls.validate_source(source)
        dedup_key = cls._dedup_key(tenant_id, record)
        existing = DemoLead.query.filter_by(tenant_id=int(tenant_id), dedup_key=dedup_key).first()
        if existing is not None:
            return {"status": "duplicate", "lead_id": existing.id, "dedup_key": dedup_key}

        lead = DemoLead(
            organization_id=int(tenant_id),
            tenant_id=int(tenant_id),
            company_name=lead_intelligence_service._clean(record.get("company_name")) or "Unknown",
            email=lead_intelligence_service.normalize_email(record.get("email")),
            phone=lead_intelligence_service._clean(record.get("phone")) or None,
            message=lead_intelligence_service._clean(record.get("message")) or None,
            source=source,
            provenance=record.get("provenance") or {"source": source, "method": "governed_ingestion"},
            status=lead_intelligence_service._clean(record.get("status")) or "new",
            estimated_value=record.get("estimated_value") or 0,
        )
        db.session.add(lead)
        db.session.flush()
        result = lead_intelligence_service.analyze(lead, persist=True)
        return {"status": "created", "lead_id": lead.id, "dedup_key": lead.dedup_key, "evidence_digest": result["evidence_digest"]}

    @classmethod
    def ingest_many(cls, *, tenant_id: int, records: Iterable[dict[str, Any]], source: str) -> dict[str, Any]:
        items = [cls.ingest_one(tenant_id=tenant_id, record=record, source=source) for record in records]
        return {
            "success": True,
            "version": cls.VERSION,
            "tenant_id": int(tenant_id),
            "source": cls.validate_source(source),
            "created": sum(item["status"] == "created" for item in items),
            "duplicates": sum(item["status"] == "duplicate" for item in items),
            "items": items,
            "governance": {"tenant_bound": True, "allowed_sources_only": True, "external_execution": False, "human_approval_required": True},
        }


lead_discovery_service = LeadDiscoveryService()
