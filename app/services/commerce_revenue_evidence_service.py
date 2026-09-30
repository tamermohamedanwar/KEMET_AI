from __future__ import annotations

import json
from typing import Any

from app.models.payment import Payment
from app.services.commercial_outcome_trace import commercial_outcome_trace
from app.services.kemet_provenance_lineage_service import kemet_provenance_lineage_service


class CommerceRevenueEvidenceService:
    VERSION = "1.0"

    def verify(self, *, organization_id: int, execution_key: str,
               payment_id: Any = None) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        if not str(execution_key or "").strip():
            raise ValueError("execution_key_required")
        payment = None
        if payment_id is not None:
            try:
                payment = Payment.query.filter_by(
                    id=int(payment_id), organization_id=int(organization_id), status="paid"
                ).first()
            except (TypeError, ValueError):
                payment = None
            if payment is None:
                return self._blocked("recorded_payment_not_found")
        trace = commercial_outcome_trace.get(int(organization_id), str(execution_key))
        if trace is None:
            return self._blocked("execution_trace_not_found")
        business = trace.get("business") or {}
        recorded = business.get("revenue")
        bound_payment_id = None
        ledger = trace.get("trace", {}).get("ledger", {})
        job_id = ledger.get("job_id")
        if job_id is not None:
            from app.models.automation_outcome import AutomationOutcome
            outcome = AutomationOutcome.query.filter_by(
                organization_id=int(organization_id), job_id=int(job_id)
            ).order_by(AutomationOutcome.id.desc()).first()
            if outcome is not None:
                try:
                    outcome_receipt = json.loads(outcome.receipt_json or "{}")
                except (TypeError, ValueError):
                    outcome_receipt = {}
                bound_payment_id = outcome_receipt.get("revenue_record_id")
        if payment_id is not None:
            try:
                if bound_payment_id is None or int(bound_payment_id) != int(payment.id):
                    return self._blocked("payment_execution_binding_mismatch")
            except (TypeError, ValueError):
                return self._blocked("payment_execution_binding_mismatch")
        payment_evidence = None
        if payment is not None:
            from app.core.execution_evidence import execution_evidence
            payment_evidence = {
                "payment_id": payment.id,
                "amount": float(payment.amount),
                "currency": payment.currency,
                "status": payment.status,
                "provider": payment.provider,
                "provider_transaction_id": payment.provider_transaction_id,
                "provider_order_id": payment.provider_order_id,
            }
            execution_evidence.record(
                organization_id=int(organization_id), execution_key=str(execution_key),
                job_id=(trace.get("trace") or {}).get("ledger", {}).get("job_id"),
                stage="payment.completed", status="completed",
                evidence_key=f"{execution_key}:payment:{payment.id}",
                receipt=payment_evidence,
            )
            trace = commercial_outcome_trace.get(int(organization_id), str(execution_key)) or trace
            business = trace.get("business") or {}
            recorded = business.get("revenue")
        lineage = None
        if payment_evidence is not None:
            lineage = kemet_provenance_lineage_service.commerce_chain(
                organization_id=int(organization_id),
                trace_id=str(execution_key),
                execution_key=str(execution_key),
                payment_evidence=payment_evidence,
            )
        return {
            "success": True,
            "status": "verified",
            "engine": "kemet_commerce_revenue_evidence",
            "provenance_lineage": lineage,
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "execution_key": str(execution_key),
            "evidence": {"payment": payment_evidence, "trace_revenue": recorded},
            "commercial": {
                "revenue": recorded if recorded is not None else "not_available",
                "roi": business.get("roi") if business.get("roi") is not None else "not_proven",
                "causal_claim": False,
            },
            "governance": {
                "read_only": True, "external_execution": False,
                "database_mutation": False, "tenant_scoped": True,
            },
        }

    @staticmethod
    def _blocked(reason: str) -> dict[str, Any]:
        return {
            "success": False, "status": "blocked", "error": reason,
            "commercial": {"revenue": "not_available", "roi": "not_proven", "causal_claim": False},
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
        }


commerce_revenue_evidence_service = CommerceRevenueEvidenceService()
