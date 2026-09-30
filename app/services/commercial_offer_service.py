from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from app import db
from app.models.commercial_offer import CommercialOffer
from app.models.demo_lead import DemoLead
from app.models.revenue_pipeline import RevenuePipelineRecord
from app.services.revenue_pipeline_service import revenue_pipeline_service


class CommercialOfferService:
    VERSION = "1.1"
    REQUIRED_QUALIFICATION = (
        "desired_service",
        "business_need",
        "scope",
        "target_deadline",
        "decision_authority",
    )

    @staticmethod
    def _text(value: Any, error: str, limit: int = 1000) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError(error)
        return value[:limit]

    @staticmethod
    def _money(value: Any) -> Decimal:
        try:
            amount = Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("invalid_offer_amount") from exc
        if amount <= 0:
            raise ValueError("offer_amount_must_be_positive")
        return amount.quantize(Decimal("0.01"))

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _record(organization_id: int, pipeline_key: str) -> RevenuePipelineRecord:
        return revenue_pipeline_service._record(int(organization_id), str(pipeline_key))

    def qualification_state(self, *, organization_id: int, pipeline_key: str) -> dict[str, Any]:
        record = self._record(organization_id, pipeline_key)
        metadata = dict(record.metadata_json or {})
        qualification = metadata.get("commercial_qualification") or {}
        complete = all(str(qualification.get(field) or "").strip() for field in self.REQUIRED_QUALIFICATION)
        return {
            "status": "qualified" if complete else "qualification_required",
            "complete": complete,
            "required_fields": list(self.REQUIRED_QUALIFICATION),
            "provided_fields": [field for field in self.REQUIRED_QUALIFICATION if str(qualification.get(field) or "").strip()],
            "qualification": qualification,
            "governance": {"external_execution": False, "auto_execute": False, "human_approval_required": bool(offer.approval_required)},
        }

    def qualify(self, *, organization_id: int, pipeline_key: str, qualification: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(qualification, Mapping):
            raise ValueError("qualification_required")
        record = self._record(organization_id, pipeline_key)
        lead = db.session.get(DemoLead, record.lead_id)
        if not lead or int(lead.organization_id or 0) != int(organization_id):
            raise ValueError("lead_organization_mismatch")
        data = {
            field: self._text(qualification.get(field), f"{field}_required", 1000)
            for field in self.REQUIRED_QUALIFICATION
        }
        evidence = qualification.get("evidence")
        if isinstance(evidence, Mapping):
            data["evidence"] = dict(evidence)
        data["source"] = "human_supplied"
        data["status"] = "qualified"
        metadata = dict(record.metadata_json or {})
        metadata["commercial_qualification"] = data
        record.metadata_json = metadata
        lead.qualification_status = "commercial_qualified"
        lead.qualification_reason = json.dumps(data, sort_keys=True, ensure_ascii=False)
        lead.status = "qualified"
        if record.stage == "inquiry":
            revenue_pipeline_service._transition(record, "qualified")
        elif record.stage != "qualified":
            raise ValueError("qualification_requires_inquiry_stage")
        db.session.commit()
        return self.qualification_state(organization_id=organization_id, pipeline_key=pipeline_key)

    def draft_offer(self, *, organization_id: int, pipeline_key: str, offer_name: str,
                    offer_description: str, quoted_amount: Any, currency: str = "EGP") -> dict[str, Any]:
        record = self._record(organization_id, pipeline_key)
        state = self.qualification_state(organization_id=organization_id, pipeline_key=pipeline_key)
        if not state["complete"]:
            raise ValueError("qualification_required_before_offer")
        if record.stage != "qualified":
            raise ValueError("offer_requires_qualified_pipeline")
        name = self._text(offer_name, "offer_name_required", 255)
        description = self._text(offer_description, "offer_description_required", 5000)
        amount = self._money(quoted_amount)
        currency = str(currency or "EGP").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("invalid_offer_currency")
        existing = CommercialOffer.query.filter_by(
            organization_id=int(organization_id), pipeline_id=record.id
        ).first()
        if existing:
            return self.snapshot(existing)
        provenance = {
            "source": "human_qualified_lead",
            "organization_id": int(organization_id),
            "lead_id": int(record.lead_id),
            "pipeline_id": int(record.id),
            "qualification": state["qualification"],
        }
        payload = {
            "organization_id": int(organization_id), "lead_id": int(record.lead_id),
            "pipeline_id": int(record.id), "offer_name": name,
            "offer_description": description, "quoted_amount": str(amount), "currency": currency,
            "status": "draft", "approval_required": True,
        }
        offer = CommercialOffer(
            organization_id=int(organization_id), lead_id=int(record.lead_id), pipeline_id=int(record.id),
            offer_name=name, offer_description=description, quoted_amount=amount, currency=currency,
            status="draft", approval_required=True, evidence_provenance=provenance,
            approval_package_hash=self._digest(payload),
        )
        db.session.add(offer)
        record.offer_name = name
        record.quoted_amount = amount
        record.currency = currency
        revenue_pipeline_service._transition(record, "proposal")
        db.session.flush()
        from app.services.automation_approval_service import automation_approval_service
        approval = automation_approval_service.create(
            organization_id=int(organization_id),
            action_type="commercial_offer_approval",
            reason="Human approval required before sending this commercial offer externally.",
            request_data={
                "action": "commercial_offer_approval",
                "parameters": {"offer_id": int(offer.id), "approval_package_hash": offer.approval_package_hash},
                "data": {"offer_id": int(offer.id), "pipeline_id": int(record.id)},
            },
            requested_by=None,
        )
        if not approval.get("success"):
            db.session.rollback()
            raise RuntimeError("commercial_offer_approval_creation_failed")
        provenance["approval_id"] = int(approval["approval_id"])
        offer.evidence_provenance = provenance
        db.session.commit()
        return self.snapshot(offer)

    def approve(self, *, organization_id: int, offer_id: int, approver_id: int) -> dict[str, Any]:
        offer = db.session.get(CommercialOffer, int(offer_id))
        if not offer or int(offer.organization_id) != int(organization_id):
            raise ValueError("offer_not_found")
        if offer.status != "draft":
            return self.snapshot(offer)
        approval_id = int((offer.evidence_provenance or {}).get("approval_id") or 0)
        if not approval_id:
            raise ValueError("commercial_offer_approval_missing")
        from app.services.bos_runtime import bos_runtime
        result = bos_runtime.approve(approval_id, int(organization_id), int(approver_id))
        if not result.get("success"):
            return result
        offer.status = "approved"
        offer.approval_required = False
        provenance = dict(offer.evidence_provenance or {})
        provenance["approved_by"] = int(approver_id)
        offer.evidence_provenance = provenance
        db.session.commit()
        return self.snapshot(offer)

    @staticmethod
    def snapshot(offer: CommercialOffer) -> dict[str, Any]:
        return {
            "success": True, "version": CommercialOfferService.VERSION, "id": offer.id,
            "organization_id": offer.organization_id, "lead_id": offer.lead_id, "pipeline_id": offer.pipeline_id,
            "offer_name": offer.offer_name, "offer_description": offer.offer_description,
            "quoted_amount": float(offer.quoted_amount), "currency": offer.currency,
            "status": offer.status, "approval_required": bool(offer.approval_required),
            "approval_id": (offer.evidence_provenance or {}).get("approval_id"),
            "approval_package_hash": offer.approval_package_hash,
            "evidence_provenance": offer.evidence_provenance,
            "governance": {"external_execution": False, "auto_execute": False, "human_approval_required": bool(offer.approval_required)},
        }


commercial_offer_service = CommercialOfferService()
