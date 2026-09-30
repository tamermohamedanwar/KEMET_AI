from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app import db
from app.core.evidence.fabric import execution_evidence_fabric
from app.models.demo_lead import DemoLead
from app.models.lead_intelligence_evidence import LeadIntelligenceEvidence
from app.services.lead_intelligence_service import lead_intelligence_service


class BusinessIntelligencePipelineService:
    """Deterministic, tenant-bound advisory BI pipeline for canonical leads."""

    VERSION = "1.0"
    SCHEMA = "kemet.business_intelligence.v1"

    @staticmethod
    def _digest(value: Any) -> str:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _enrichment(cls, canonical: dict[str, Any]) -> dict[str, Any]:
        identity = canonical["identity"]
        context = canonical["context"]
        commercial = canonical["commercial"]
        fields = {
            "company": identity["company"],
            "email": identity["email"],
            "phone": identity["phone"],
            "status": context["status"],
            "estimated_value": commercial["estimated_value"],
        }
        items = {}
        missing = []
        for field, value in fields.items():
            present = value not in (None, "", 0, 0.0)
            items[field] = {
                "value": value if present else None,
                "source": "canonical_lead",
                "source_type": "explicit_record",
                "confidence": 1.0 if present else 0.0,
                "freshness": canonical.get("freshness", ""),
                "evidence": {"field_present": present},
                "provenance": canonical.get("provenance", {}),
            }
            if not present:
                missing.append(field)
        return {"fields": items, "missing_data": missing, "method": "explicit_record_enrichment_v1"}

    @classmethod
    def _quality(cls, enrichment: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any]:
        fields = enrichment["fields"]
        total = max(len(fields), 1)
        present = sum(item["value"] not in (None, "", 0, 0.0) for item in fields.values())
        completeness = round(present / total, 4)
        freshness = 1.0 if canonical.get("freshness") else 0.0
        provenance = 1.0 if canonical.get("provenance") else 0.0
        validity = 1.0
        uniqueness = 1.0 if canonical.get("dedup_key") else 0.0
        dimensions = {
            "completeness": completeness,
            "validity": validity,
            "consistency": 1.0,
            "uniqueness": uniqueness,
            "freshness": freshness,
            "provenance": provenance,
        }
        score = round(sum(dimensions.values()) / len(dimensions), 4)
        return {"quality_score": score, "quality_dimensions": dimensions, "missing_fields": list(enrichment["missing_data"]), "method": "deterministic_data_quality_v1"}

    @classmethod
    def _segment(cls, qualification: dict[str, Any], scoring: dict[str, Any], quality: dict[str, Any], enrichment: dict[str, Any]) -> dict[str, Any]:
        score = float(scoring["score"])
        confidence = float(qualification["confidence"])
        missing = enrichment["missing_data"]
        if missing and (len(missing) >= 2 or quality["quality_score"] < 0.70):
            segment, reason = "needs_enrichment", "Material lead data is missing."
        elif score >= 75 and confidence >= 0.60:
            segment, reason = "high_intent", "Strong evidence-based score and qualification confidence."
        elif score >= 45:
            segment, reason = "qualified", "Lead has sufficient evidence for qualified review."
        else:
            segment, reason = "low_signal", "Available evidence does not support a stronger segment."
        return {"segment": segment, "reason": reason, "evidence": scoring["evidence"], "confidence": round(min(confidence, quality["quality_score"]), 4), "rules": {"version": "segment_rules_v1", "score": score, "qualification_confidence": confidence}, "version": "1.0"}

    @classmethod
    def _decision(cls, canonical, qualification, scoring, segment, quality, enrichment):
        missing = list(enrichment["missing_data"])
        if segment["segment"] == "needs_enrichment":
            decision, action = "enrich_first", "enrich_lead"
        elif segment["segment"] == "high_intent":
            decision, action = "contact_now", "review_lead"
        elif segment["segment"] == "qualified":
            decision, action = "review_required", "review_lead"
        else:
            decision, action = "nurture", "monitor_lead"
        confidence = round(min(float(segment["confidence"]), quality["quality_score"]), 4)
        rationale = segment["reason"]
        if missing:
            rationale = f"{rationale} Missing data: {', '.join(missing)}."
        return {
            "decision": decision,
            "rationale": rationale,
            "confidence": confidence,
            "evidence": scoring["evidence"],
            "missing_data": missing,
            "recommended_next_step": action,
            "version": "decision_rules_v1",
            "advisory": True,
        }

    @classmethod
    def _record_evidence(cls, tenant_id, lead_id, operation, before, after, package):
        before_digest = cls._digest(before)
        after_digest = cls._digest(after)
        evidence_digest = execution_evidence_fabric.digest({**package, "before_digest": before_digest, "after_digest": after_digest})
        existing = LeadIntelligenceEvidence.query.filter_by(
            tenant_id=tenant_id, lead_id=lead_id, operation=operation, after_digest=after_digest
        ).first()
        if existing is None:
            db.session.add(LeadIntelligenceEvidence(
                tenant_id=tenant_id, lead_id=lead_id, operation=operation,
                before_digest=before_digest, after_digest=after_digest,
                evidence_digest=evidence_digest,
                evidence_json=json.dumps({**package, "before_digest": before_digest, "after_digest": after_digest}, sort_keys=True, ensure_ascii=False),
            ))
        return evidence_digest

    @classmethod
    def build(cls, lead, *, persist_evidence: bool = True) -> dict[str, Any]:
        canonical = lead_intelligence_service.canonicalize(lead)
        tenant_id = canonical["tenant_id"]
        enrichment = cls._enrichment(canonical)
        quality = cls._quality(enrichment, canonical)
        qualification = lead_intelligence_service.qualification(canonical)
        scoring = lead_intelligence_service.score_from_evidence(canonical, qualification)
        segment = cls._segment(qualification, scoring, quality, enrichment)
        decision = cls._decision(canonical, qualification, scoring, segment, quality, enrichment)
        base = {
            "schema": cls.SCHEMA, "version": cls.VERSION, "tenant_id": tenant_id,
            "lead_id": canonical["lead_id"], "canonical_lead": canonical,
            "enrichment": enrichment, "data_quality": quality,
            "qualification": qualification, "score": scoring,
            "segment": segment, "decision": decision,
            "confidence": decision["confidence"], "missing_data": decision["missing_data"],
            "explanation": decision["rationale"], "provenance": canonical["provenance"],
            "freshness": canonical["freshness"],
        }
        stage_digests = {}
        if persist_evidence:
            stages = (
                ("bi_enrichment", {"canonical": canonical}, {"enrichment": enrichment, "data_quality": quality}),
                ("bi_segmentation", {"enrichment": enrichment, "score": scoring}, {"segment": segment}),
                ("bi_decision", {"segment": segment, "quality": quality}, {"decision": decision}),
            )
            for operation, before, after in stages:
                stage_digests[operation] = cls._record_evidence(
                    tenant_id, canonical["lead_id"], operation,
                    before, after,
                    {"schema": cls.SCHEMA, "version": cls.VERSION, "operation": operation,
                     "tenant_id": tenant_id, "lead_id": canonical["lead_id"], "timestamp": cls._now(), "after": after},
                )
        final_digest = execution_evidence_fabric.digest(base)
        return {**base, "evidence_digest": final_digest, "stage_evidence": stage_digests,
                "governance": {"advisory": True, "read_only": not persist_evidence, "external_execution": False,
                               "auto_execute": False, "human_approval_required": True, "replayable": True}}

    @classmethod
    def build_for_lead_id(cls, tenant_id: int, lead_id: int, *, persist_evidence: bool = True):
        lead = DemoLead.query.filter_by(id=int(lead_id), tenant_id=int(tenant_id)).first()
        if lead is None:
            raise ValueError("lead_not_found")
        return cls.build(lead, persist_evidence=persist_evidence)


business_intelligence_pipeline = BusinessIntelligencePipelineService()
