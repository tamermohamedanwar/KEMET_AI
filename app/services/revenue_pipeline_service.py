from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from app import db
from app.models.demo_lead import DemoLead
from app.models.payment import Payment
from app.models.revenue_pipeline import RevenuePipelineRecord


class RevenuePipelineService:
    VERSION = "1.0"
    STAGES = (
        "inquiry", "qualified", "proposal", "awaiting_payment",
        "paid", "fulfillment", "delivered", "closed", "lost", "refunded",
    )
    TRANSITIONS = {
        "inquiry": {"qualified", "lost"},
        "qualified": {"proposal", "lost"},
        "proposal": {"awaiting_payment", "lost"},
        "awaiting_payment": {"paid", "lost"},
        "paid": {"fulfillment", "refunded"},
        "fulfillment": {"delivered", "lost", "refunded"},
        "delivered": {"closed", "refunded"},
        "closed": {"refunded"},
        "lost": {"qualified", "proposal"},
        "refunded": set(),
    }

    @staticmethod
    def _money(value: Any) -> Decimal:
        try:
            result = Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("invalid_money") from exc
        if result < 0:
            raise ValueError("money_must_be_non_negative")
        return result.quantize(Decimal("0.01"))

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = repr(sorted((str(k), str(v)) for k, v in payload.items())).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def _record(cls, organization_id: int, pipeline_key: str) -> RevenuePipelineRecord:
        record = RevenuePipelineRecord.query.filter_by(
            organization_id=int(organization_id), pipeline_key=str(pipeline_key)
        ).first()
        if not record:
            raise ValueError("revenue_pipeline_not_found")
        return record

    @classmethod
    def _transition(cls, record: RevenuePipelineRecord, target: str) -> None:
        target = str(target or "").strip().lower()
        if target not in cls.STAGES:
            raise ValueError("invalid_revenue_stage")
        if target == record.stage:
            return
        allowed = cls.TRANSITIONS.get(record.stage, set())
        if target not in allowed:
            raise ValueError("invalid_revenue_stage_transition")
        history = list(record.stage_history or [])
        history.append({
            "from": record.stage,
            "to": target,
            "at": datetime.utcnow().isoformat(),
        })
        record.stage_history = history
        record.stage = target

    @classmethod
    def intake(cls, *, organization_id: int, company_name: str, email: str,
               phone: str = "", message: str = "", source: str = "command_center",
               offer_name: str = "", quoted_amount: Any = 0, pipeline_key: str = "") -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        company_name = str(company_name or "").strip()
        email = str(email or "").strip()
        if not company_name or not email:
            raise ValueError("customer_identity_required")
        amount = cls._money(quoted_amount)
        if pipeline_key:
            key = str(pipeline_key).strip()
        else:
            key = hashlib.sha256(
                f"{int(organization_id)}:{email.lower()}:{offer_name}:{message}".encode("utf-8")
            ).hexdigest()[:48]
        existing = RevenuePipelineRecord.query.filter_by(
            organization_id=int(organization_id), pipeline_key=key
        ).first()
        if existing:
            return cls.snapshot(existing)
        lead = DemoLead(
            organization_id=int(organization_id), tenant_id=int(organization_id),
            company_name=company_name, email=email, phone=str(phone or "").strip() or None,
            message=str(message or "").strip() or None, source=str(source or "command_center"),
            status="new", estimated_value=amount,
        )
        db.session.add(lead)
        db.session.flush()
        record = RevenuePipelineRecord(
            organization_id=int(organization_id), lead_id=lead.id, pipeline_key=key,
            stage="inquiry", source=str(source or "command_center"),
            offer_name=str(offer_name or "").strip() or None, quoted_amount=amount,
            stage_history=[], metadata_json={"customer": {"company_name": company_name, "email": email}},
        )
        db.session.add(record)
        db.session.commit()
        return cls.snapshot(record)

    @classmethod
    def intake_telegram_prospect(cls, *, organization_id: int, telegram_user_id: str, telegram_chat_id: str, telegram_message_id: str, company_name: str, email: str, message: str = "") -> dict[str, Any]:
        """Create a tenant-scoped inquiry from explicit Telegram prospect data only."""
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        user_id = str(telegram_user_id or "").strip()
        chat_id = str(telegram_chat_id or "").strip()
        message_id = str(telegram_message_id or "").strip()
        company_name = str(company_name or "").strip()
        email = str(email or "").strip().lower()
        if not user_id or not chat_id or not message_id:
            raise ValueError("telegram_identity_required")
        if not company_name or not email:
            raise ValueError("telegram_commercial_identity_required")
        key = hashlib.sha256(f"telegram:{int(organization_id)}:{chat_id}:{message_id}".encode("utf-8")).hexdigest()[:48]
        existing = cls._record_or_none(int(organization_id), key)
        if existing:
            return cls.snapshot(existing)
        lead = DemoLead(
            organization_id=int(organization_id), tenant_id=int(organization_id),
            company_name=company_name, email=email, message=str(message or "").strip() or None,
            source="telegram", status="new", estimated_value=Decimal("0.00"),
            provenance={"source": "telegram", "method": "verified_webhook", "telegram_user_id": user_id, "telegram_chat_id": chat_id, "telegram_message_id": message_id},
        )
        db.session.add(lead)
        db.session.flush()
        from app.services.lead_intelligence_service import lead_intelligence_service
        lead_intelligence_service.analyze(lead, persist=True)
        record = RevenuePipelineRecord(
            organization_id=int(organization_id), lead_id=lead.id, pipeline_key=key,
            stage="inquiry", source="telegram", offer_name=None, quoted_amount=Decimal("0.00"),
            stage_history=[], metadata_json={"channel": "telegram", "telegram": {"user_id": user_id, "chat_id": chat_id, "message_id": message_id}},
        )
        db.session.add(record)
        db.session.commit()
        return cls.snapshot(record)

    @classmethod
    def intake_whatsapp_prospect(cls, *, organization_id: int, whatsapp_user_id: str, whatsapp_message_id: str, company_name: str, email: str, phone: str = "", message: str = "") -> dict:
        """Create a tenant-scoped WhatsApp inquiry from explicitly supplied identity."""
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        user_id = str(whatsapp_user_id or "").strip()
        message_id = str(whatsapp_message_id or "").strip()
        company_name = str(company_name or "").strip()
        email = str(email or "").strip().lower()
        if not user_id or not message_id:
            raise ValueError("whatsapp_identity_required")
        if not company_name or not email:
            raise ValueError("whatsapp_commercial_identity_required")
        key = hashlib.sha256(f"whatsapp:{int(organization_id)}:{user_id}:{message_id}".encode("utf-8")).hexdigest()[:48]
        existing = cls._record_or_none(int(organization_id), key)
        if existing:
            return cls.snapshot(existing)
        lead = DemoLead(
            organization_id=int(organization_id), tenant_id=int(organization_id),
            company_name=company_name, email=email, phone=str(phone or user_id).strip() or None,
            message=str(message or "").strip() or None, source="whatsapp", status="new", estimated_value=Decimal("0.00"),
            provenance={"source": "whatsapp", "method": "verified_webhook", "whatsapp_user_id": user_id, "whatsapp_message_id": message_id},
        )
        db.session.add(lead)
        db.session.flush()
        record = RevenuePipelineRecord(
            organization_id=int(organization_id), lead_id=lead.id, pipeline_key=key,
            stage="inquiry", source="whatsapp", offer_name=None, quoted_amount=Decimal("0.00"),
            stage_history=[], metadata_json={"channel": "whatsapp", "whatsapp": {"user_id": user_id, "message_id": message_id, "phone": str(phone or user_id).strip()}},
        )
        db.session.add(record)
        db.session.commit()
        return cls.snapshot(record)

    @classmethod
    def _record_or_none(cls, organization_id: int, pipeline_key: str):
        return RevenuePipelineRecord.query.filter_by(organization_id=int(organization_id), pipeline_key=str(pipeline_key)).first()

    @classmethod
    def advance(cls, *, organization_id: int, pipeline_key: str, stage: str) -> dict[str, Any]:
        record = cls._record(organization_id, pipeline_key)
        target_stage = str(stage or "").strip().lower()
        if target_stage == "paid":
            raise ValueError("paid_stage_requires_verified_payment")
        cls._transition(record, target_stage)
        if record.lead_id:
            lead = db.session.get(DemoLead, record.lead_id)
            if lead and stage == "qualified":
                lead.status = "qualified"
            elif lead and stage == "proposal":
                lead.status = "proposal"
            elif lead and stage == "lost":
                lead.status = "lost"
            elif lead and stage in {"paid", "fulfillment", "delivered", "closed"}:
                lead.status = "won"
                lead.converted_at = lead.converted_at or datetime.utcnow()
        db.session.commit()
        return cls.snapshot(record)

    @classmethod
    def attach_payment(cls, *, organization_id: int, pipeline_key: str, payment_id: int) -> dict[str, Any]:
        record = cls._record(organization_id, pipeline_key)
        payment = db.session.get(Payment, int(payment_id))
        if not payment or int(payment.organization_id) != int(organization_id):
            raise ValueError("payment_organization_mismatch")
        if str(payment.status or "").lower() != "paid":
            raise ValueError("payment_not_completed")
        transaction_id = str(payment.provider_transaction_id or "").strip()
        if not transaction_id:
            raise ValueError("payment_transaction_id_required")
        if record.payment_id or record.payment_transaction_id:
            raise ValueError("payment_already_bound")
        expected_amount = cls._money(record.quoted_amount)
        paid_amount = cls._money(payment.amount)
        if paid_amount != expected_amount:
            raise ValueError("payment_amount_mismatch")
        expected_currency = str(record.currency or "EGP").strip().upper()
        payment_currency = str(payment.currency or "").strip().upper()
        if payment_currency != expected_currency:
            raise ValueError("payment_currency_mismatch")
        if record.stage != "awaiting_payment":
            raise ValueError("payment_requires_awaiting_payment")
        record.payment_id = payment.id
        record.payment_transaction_id = transaction_id
        record.paid_amount = cls._money(payment.amount)
        cls._transition(record, "paid")
        record.evidence_digest = cls._digest({
            "organization_id": organization_id, "pipeline_key": pipeline_key,
            "payment_id": payment.id, "transaction_id": transaction_id,
            "paid_amount": str(record.paid_amount),
        })
        db.session.commit()
        return cls.snapshot(record)

    @classmethod
    def record_cost(cls, *, organization_id: int, pipeline_key: str, category: str, amount: Any) -> dict[str, Any]:
        record = cls._record(organization_id, pipeline_key)
        value = cls._money(amount)
        category = str(category or "").strip().lower()
        if category == "acquisition":
            record.acquisition_cost = cls._money(record.acquisition_cost) + value
        elif category == "fulfillment":
            record.fulfillment_cost = cls._money(record.fulfillment_cost) + value
        elif category in {"provider_fee", "provider_fees"}:
            record.provider_fees = cls._money(record.provider_fees) + value
        elif category == "refund":
            record.refunds = cls._money(record.refunds) + value
        else:
            raise ValueError("unsupported_cost_category")
        db.session.commit()
        return cls.snapshot(record)

    @classmethod
    def attach_delivery(cls, *, organization_id: int, pipeline_key: str, fulfillment_reference: str) -> dict[str, Any]:
        record = cls._record(organization_id, pipeline_key)
        reference = str(fulfillment_reference or "").strip()
        if not reference:
            raise ValueError("fulfillment_reference_required")
        if record.stage not in {"paid", "fulfillment"}:
            raise ValueError("payment_required_before_delivery")
        if record.stage == "paid":
            cls._transition(record, "fulfillment")
        record.fulfillment_reference = reference
        record.delivered_at = datetime.utcnow()
        cls._transition(record, "delivered")
        db.session.commit()
        return cls.snapshot(record)

    @classmethod
    def close(cls, *, organization_id: int, pipeline_key: str) -> dict[str, Any]:
        record = cls._record(organization_id, pipeline_key)
        cls._transition(record, "closed")
        record.closed_at = datetime.utcnow()
        db.session.commit()
        return cls.snapshot(record)

    @classmethod
    def snapshot(cls, record: RevenuePipelineRecord) -> dict[str, Any]:
        paid = cls._money(record.paid_amount)
        costs = sum((cls._money(x) for x in (
            record.acquisition_cost, record.fulfillment_cost, record.provider_fees, record.refunds
        )), Decimal("0.00"))
        profit_verified = bool(record.payment_id and paid > 0)
        profit = (paid - costs) if profit_verified else Decimal("0.00")
        margin = (profit / paid * Decimal("100")) if profit_verified and paid > 0 else Decimal("0.00")
        return {
            "success": True, "version": cls.VERSION, "id": record.id,
            "organization_id": record.organization_id, "lead_id": record.lead_id,
            "pipeline_key": record.pipeline_key, "stage": record.stage,
            "source": record.source, "offer_name": record.offer_name,
            "currency": record.currency, "quoted_amount": float(record.quoted_amount or 0),
            "paid_amount": float(paid),
            "costs": {
                "acquisition": float(record.acquisition_cost or 0),
                "fulfillment": float(record.fulfillment_cost or 0),
                "provider_fees": float(record.provider_fees or 0),
                "refunds": float(record.refunds or 0),
                "total": float(costs),
            },
            "profit": float(profit), "margin_pct": float(margin.quantize(Decimal("0.01"))),
            "profit_status": "verified" if profit_verified else "not_verified",
            "financial_evidence": {
                "revenue_source": "bound_paid_payment" if profit_verified else "none",
                "cost_source": "recorded_pipeline_costs",
                "server_derived": True,
                "claimed_profit_accepted": False,
            },
            "payment": {"id": record.payment_id, "transaction_id": record.payment_transaction_id},
            "delivery": {"reference": record.fulfillment_reference, "delivered_at": record.delivered_at.isoformat() if record.delivered_at else None},
            "evidence_digest": record.evidence_digest,
            "stage_history": list(record.stage_history or []),
            "governance": {"tenant_scoped": True, "server_derived_payment": True, "server_derived_profit": True, "external_execution": False, "human_approval_required_for_external_actions": True},
        }

    @classmethod
    def dashboard(cls, organization_id: int) -> dict[str, Any]:
        records = RevenuePipelineRecord.query.filter_by(organization_id=int(organization_id)).all()
        snapshots = [cls.snapshot(r) for r in records]
        paid = sum(x["paid_amount"] for x in snapshots)
        costs = sum(x["costs"]["total"] for x in snapshots)
        verified_snapshots = [x for x in snapshots if x.get("profit_status") == "verified"]
        verified_paid = sum(x["paid_amount"] for x in verified_snapshots)
        verified_costs = sum(x["costs"]["total"] for x in verified_snapshots)
        profit = verified_paid - verified_costs
        return {
            "success": True, "version": cls.VERSION, "organization_id": int(organization_id),
            "pipeline_count": len(records), "stages": {stage: sum(1 for x in snapshots if x["stage"] == stage) for stage in cls.STAGES},
            "financials": {
                "paid_revenue": round(paid, 2),
                "total_cost": round(costs, 2),
                "verified_profit": round(profit, 2),
                "net_profit": round(profit, 2),
                "margin_pct": round((profit / verified_paid * 100) if verified_paid else 0, 2),
                "profit_status": "verified" if verified_snapshots else "not_verified",
                "unverified_cost": round(costs - verified_costs, 2),
            },
            "records": snapshots,
        }


revenue_pipeline_service = RevenuePipelineService()
