from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app import db
from app.core.evidence.fabric import execution_evidence_fabric
from app.models.lead_intelligence_evidence import LeadIntelligenceEvidence


class LeadIntelligenceService:
    """Canonical, tenant-bound, evidence-backed lead intelligence."""

    VERSION = "1.0"
    QUALIFICATION_RULES = (
        ("identity", 0.20),
        ("contactability", 0.20),
        ("business_context", 0.20),
        ("intent", 0.20),
        ("commercial_signal", 0.20),
    )

    @staticmethod
    def _digest(value: Any) -> str:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _clean(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())

    @classmethod
    def normalize_email(cls, value: Any) -> str:
        return cls._clean(value).lower()

    @classmethod
    def normalize_phone(cls, value: Any) -> str:
        return re.sub(r"\D+", "", cls._clean(value))

    @classmethod
    def normalize_company(cls, value: Any) -> str:
        return cls._clean(value).lower()

    @classmethod
    def _money(cls, value: Any) -> float:
        try:
            return float(Decimal(str(value or 0)))
        except (InvalidOperation, TypeError, ValueError):
            return 0.0

    @classmethod
    def canonicalize(cls, lead) -> dict[str, Any]:
        raw_tenant = getattr(lead, "tenant_id", None)
        raw_organization = getattr(lead, "organization_id", None)
        tenant_id = int(raw_tenant or raw_organization or 0)
        if tenant_id <= 0:
            raise ValueError("tenant_id_required")
        if raw_tenant is not None and raw_organization is not None and int(raw_tenant) != int(raw_organization):
            raise ValueError("tenant_organization_mismatch")
        email = cls.normalize_email(getattr(lead, "email", None))
        phone = cls.normalize_phone(getattr(lead, "phone", None))
        company = cls.normalize_company(getattr(lead, "company_name", None))
        source = cls._clean(getattr(lead, "source", None)).lower() or "unknown"
        freshness = getattr(lead, "freshness_at", None) or getattr(lead, "updated_at", None) or getattr(lead, "created_at", None)
        freshness_iso = freshness.isoformat() if hasattr(freshness, "isoformat") else str(freshness or "")
        canonical = {
            "schema": "kemet.canonical_lead.v1",
            "lead_id": int(lead.id),
            "tenant_id": tenant_id,
            "identity": {"company": company, "email": email, "phone": phone},
            "context": {"message": cls._clean(getattr(lead, "message", None)), "status": cls._clean(getattr(lead, "status", None)).lower() or "new"},
            "commercial": {"estimated_value": cls._money(getattr(lead, "estimated_value", 0))},
            "source": source,
            "provenance": getattr(lead, "provenance", None) or {"source": source, "method": "crm_record"},
            "freshness": freshness_iso,
        }
        canonical["dedup_key"] = cls._digest({"tenant_id": tenant_id, "email": email, "phone": phone, "company": company})
        return canonical

    @classmethod
    def qualification(cls, canonical: dict[str, Any]) -> dict[str, Any]:
        identity = canonical["identity"]
        context = canonical["context"]
        commercial = canonical["commercial"]
        checks = {
            "identity": bool(identity["company"] or identity["email"]),
            "contactability": bool(identity["email"] or identity["phone"]),
            "business_context": len(context["message"]) >= 20,
            "intent": context["status"] not in {"lost", "new"} or len(context["message"]) >= 40,
            "commercial_signal": commercial["estimated_value"] > 0,
        }
        score = round(sum(weight for name, weight in cls.QUALIFICATION_RULES if checks[name]), 4)
        missing = [name for name, _ in cls.QUALIFICATION_RULES if not checks[name]]
        status = "qualified" if score >= 0.60 else "review" if score >= 0.40 else "unqualified"
        return {"status": status, "confidence": score, "checks": checks, "missing": missing, "method": "evidence_rule_v1"}

    @classmethod
    def score_from_evidence(cls, canonical: dict[str, Any], qualification: dict[str, Any]) -> dict[str, Any]:
        evidence = {
            "contactability": bool(canonical["identity"]["email"] or canonical["identity"]["phone"]),
            "business_context": len(canonical["context"]["message"]) >= 20,
            "commercial_signal": canonical["commercial"]["estimated_value"] > 0,
            "qualification_confidence": qualification["confidence"],
        }
        weighted = (0.25 * float(evidence["contactability"])) + (0.25 * float(evidence["business_context"])) + (0.20 * float(evidence["commercial_signal"])) + (0.30 * float(evidence["qualification_confidence"]))
        score = round(min(max(weighted * 100, 0), 100), 2)
        temperature = "hot" if score >= 75 else "warm" if score >= 45 else "cold"
        return {"score": score, "temperature": temperature, "evidence": evidence, "method": "evidence_weighted_v1"}

    @classmethod
    def analyze(cls, lead, *, persist: bool = True) -> dict[str, Any]:
        canonical = cls.canonicalize(lead)
        qualification = cls.qualification(canonical)
        scoring = cls.score_from_evidence(canonical, qualification)
        package = {
            "version": cls.VERSION,
            "type": "lead_intelligence_transformation",
            "operation": "canonicalize_qualify_score",
            "tenant_id": canonical["tenant_id"],
            "lead_id": canonical["lead_id"],
            "canonical": canonical,
            "qualification": qualification,
            "scoring": scoring,
        }
        evidence_digest = execution_evidence_fabric.digest(package)
        result = {
            **package,
            "evidence_digest": evidence_digest,
            "governance": {"read_only": not persist, "advisory": True, "external_execution": False, "auto_execute": False, "human_approval_required": True},
        }
        if persist:
            before = cls._digest({"lead_score": lead.lead_score, "confidence": getattr(lead, "confidence", None), "dedup_key": getattr(lead, "dedup_key", None)})
            lead.tenant_id = canonical["tenant_id"]
            lead.dedup_key = canonical["dedup_key"]
            lead.provenance = canonical["provenance"]
            lead.freshness_at = datetime.utcnow()
            lead.confidence = qualification["confidence"]
            lead.qualification_status = qualification["status"]
            lead.qualification_reason = json.dumps(qualification, sort_keys=True, ensure_ascii=False)
            lead.lead_score = int(round(scoring["score"]))
            lead.evidence_digest = evidence_digest
            after = cls._digest({"lead_score": lead.lead_score, "confidence": lead.confidence, "dedup_key": lead.dedup_key})
            evidence = {**package, "before_digest": before, "after_digest": after}
            existing = LeadIntelligenceEvidence.query.filter_by(
                tenant_id=canonical["tenant_id"],
                lead_id=canonical["lead_id"],
                operation="canonicalize_qualify_score",
                after_digest=after,
            ).first()
            if existing is None:
                record = LeadIntelligenceEvidence(
                    tenant_id=canonical["tenant_id"],
                    lead_id=canonical["lead_id"],
                    operation="canonicalize_qualify_score",
                    before_digest=before,
                    after_digest=after,
                    evidence_digest=evidence_digest,
                    evidence_json=json.dumps(evidence, sort_keys=True, ensure_ascii=False),
                )
                db.session.add(record)
        return result

    @classmethod
    def deduplicate_key(cls, lead) -> str:
        return cls.canonicalize(lead)["dedup_key"]


lead_intelligence_service = LeadIntelligenceService()
