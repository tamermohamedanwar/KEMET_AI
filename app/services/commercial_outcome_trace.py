from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.execution_history import execution_history
from app.models.automation_outcome import AutomationOutcome
from app.models.payment import Payment
from app.services.revenue_identity_reconciliation_service import revenue_identity_reconciliation_service


class CommercialOutcomeTraceService:
    VERSION = "1.1"

    @classmethod
    def get(cls, organization_id: int | None, execution_key: str) -> dict[str, Any] | None:
        if not organization_id or not execution_key:
            return None
        trace = execution_history.get(
            organization_id=int(organization_id),
            execution_key=str(execution_key),
        )
        if trace is None:
            return None
        ledger = trace.get("ledger") or {}
        outcome = cls._find_outcome(organization_id, ledger)
        outcome_data = cls._outcome(outcome)
        evidence = trace.get("evidence") or []
        revenue = cls._recorded_revenue(int(organization_id), outcome_data, evidence)
        roi = cls._roi(outcome_data, evidence, revenue)
        delivery = cls._delivery_evidence(evidence)
        fulfillment = cls._fulfillment_evidence(evidence)
        payment = cls._payment_evidence(evidence)
        learning = cls._learning(execution_key, outcome_data, payment, fulfillment)
        return {
            "success": True,
            "engine": "kemet_commercial_outcome_trace",
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "execution_key": str(execution_key),
            "trace": trace,
            "business": {
                "customer": cls._receipt_value(outcome_data, "customer"),
                "intent": cls._receipt_value(outcome_data, "intent"),
                "lead": cls._receipt_value(outcome_data, "lead_id"),
                "qualification": cls._receipt_value(outcome_data, "qualification"),
                "opportunity": cls._receipt_value(outcome_data, "opportunity_id"),
                "decision": cls._receipt_value(outcome_data, "decision"),
                "approval": cls._approval(ledger),
                "action": cls._receipt_value(outcome_data, "action"),
                "outcome": cls._business_outcome(outcome_data),
                "revenue": revenue,
                "cost": outcome_data.get("cost_amount"),
                "roi": roi,
                "delivery": delivery,
                "fulfillment": fulfillment,
                "payment": payment,
                "learning": learning,
            },
            "measurement": {
                "time_to_outcome_ms": outcome_data.get("duration_ms"),
                "recorded_revenue_only": True,
                "revenue_attribution": cls._revenue_attribution(outcome_data, revenue),
                "causal_claim": False,
                "roi_proven": roi is not None,
                "roi_status": "proven" if roi is not None else "not_proven",
            },
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "tenant_scoped": True,
                "fail_closed": True,
            },
        }

    @staticmethod
    def _find_outcome(organization_id: int, ledger: dict[str, Any]) -> AutomationOutcome | None:
        job_id = ledger.get("job_id")
        if job_id is None:
            return None
        return (
            AutomationOutcome.query
            .filter(
                AutomationOutcome.organization_id == int(organization_id),
                AutomationOutcome.job_id == int(job_id),
            )
            .order_by(AutomationOutcome.id.desc())
            .first()
        )

    @staticmethod
    def _outcome(outcome: AutomationOutcome | None) -> dict[str, Any]:
        if outcome is None:
            return {}
        try:
            receipt = json.loads(outcome.receipt_json or "{}")
        except (TypeError, ValueError):
            receipt = {}
        return {
            "id": outcome.id,
            "business_outcome": outcome.business_outcome,
            "duration_ms": outcome.duration_ms,
            "cost_amount": float(outcome.cost_amount) if outcome.cost_amount is not None else None,
            "currency": outcome.currency,
            "receipt": receipt,
        }

    @staticmethod
    def _receipt_value(data: dict[str, Any], key: str) -> Any:
        receipt = data.get("receipt") or {}
        if key in receipt:
            return receipt[key]
        containers = [
            receipt.get("metadata"),
            receipt.get("business_context"),
            receipt.get("data"),
            receipt.get("result"),
        ]
        for container in containers:
            if isinstance(container, dict) and key in container:
                return container[key]
            if isinstance(container, dict):
                nested = container.get("data") or container.get("result")
                if isinstance(nested, dict) and key in nested:
                    return nested[key]
        return None

    @staticmethod
    def _business_outcome(data: dict[str, Any]) -> Any:
        value = data.get("business_outcome")
        if value is not None:
            return value
        return "completed" if data.get("id") is not None else None

    @staticmethod
    def _approval(ledger: dict[str, Any]) -> dict[str, Any]:
        return {
            "present": bool(ledger.get("approval_hash")),
            "authorization_bound": bool(ledger.get("approval_hash")),
        }

    @classmethod
    def _recorded_revenue(cls, organization_id: int, data: dict[str, Any], evidence: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
        receipt = data.get("receipt") or {}
        value = receipt.get("recorded_revenue")
        source = receipt.get("revenue_source") or "recorded_outcome"
        currency = receipt.get("revenue_currency") or data.get("currency")
        for item in reversed(evidence or []):
            if item.get("stage") != "payment.completed":
                continue
            payment = item.get("receipt") or {}
            content_id = str(payment.get("content_id") or cls._receipt_value(data, "content_id") or "")
            publication_id = str(payment.get("publication_id") or cls._receipt_value(data, "publication_id") or "")
            execution_key = str(payment.get("execution_key") or cls._receipt_value(data, "execution_key") or "")
            # A commerce trace can legitimately prove payment before content/publication
            # attribution exists (for example, a direct fulfillment sale). In that case,
            # bind the paid transaction to this tenant and execution evidence directly;
            # keep content/publication reconciliation as the stronger attribution layer.
            payment_id = payment.get("payment_id")
            direct_payment = None
            if payment_id is not None:
                try:
                    direct_payment = Payment.query.filter_by(
                        id=int(payment_id), organization_id=int(organization_id), status="paid"
                    ).first()
                except (TypeError, ValueError):
                    direct_payment = None
            if direct_payment is not None and str(direct_payment.provider_transaction_id or "") == str(payment.get("provider_transaction_id") or ""):
                value = max(0.0, float(direct_payment.amount or 0))
                currency = direct_payment.currency or payment.get("currency") or currency
                source = "payment_record"
                break
            try:
                reconciliation = revenue_identity_reconciliation_service.reconcile(organization_id=int(organization_id), content_id=content_id, publication_id=publication_id, execution_key=execution_key, evidence=[item])
            except (TypeError, ValueError):
                reconciliation = {"status": "not_reconciled"}
            if reconciliation.get("status") != "reconciled":
                return {"amount": 0.0, "currency": payment.get("currency") or currency, "source": "payment_record", "evidence_backed": False, "provenance": "payment_evidence_unreconciled"}
            transactions = (reconciliation.get("identity") or {}).get("transactions") or []
            value = sum(max(0.0, float(tx.get("amount") or 0)) for tx in transactions)
            currency = payment.get("currency") or currency
            source = "payment_record"
            break
        if value is None:
            value = receipt.get("recorded_revenue")
            source = receipt.get("revenue_source") or "recorded_outcome"
        if value is None:
            return None
        try:
            amount = float(Decimal(str(value)))
        except (InvalidOperation, TypeError, ValueError):
            return None
        evidence_backed = source == "payment_record" and any(
            item.get("stage") == "payment.completed" for item in (evidence or [])
        )
        return {
            "amount": amount,
            "currency": currency,
            "source": source,
            "evidence_backed": evidence_backed,
            "provenance": "payment_evidence" if evidence_backed else "reported_outcome",
        }

    @staticmethod
    def _revenue_attribution(data: dict[str, Any], revenue: dict[str, Any] | None = None) -> dict[str, Any]:
        receipt = data.get("receipt") or {}
        return {
            "status": "recorded" if revenue is not None else "not_available",
            "source": revenue.get("source") if revenue else receipt.get("revenue_source"),
            "provenance": revenue.get("provenance") if revenue else None,
            "evidence_backed": bool(revenue and revenue.get("evidence_backed")),
            "causal_claim": False,
        }


    @staticmethod
    def _delivery_evidence(evidence: list[dict[str, Any]]) -> dict[str, Any]:
        events = []
        for item in evidence:
            if item.get("stage") != "channel.delivery":
                continue
            receipt = item.get("receipt") or {}
            events.append({
                "status": item.get("status"),
                "message_id": receipt.get("message_id"),
                "provider": receipt.get("provider"),
                "recorded_at": item.get("created_at"),
                "evidence_key": item.get("evidence_key"),
            })
        events.sort(key=lambda item: (item.get("recorded_at") or "", item.get("status") or ""))
        latest = events[-1] if events else None
        return {
            "status": latest.get("status") if latest else "not_available",
            "latest": latest,
            "events": events,
            "evidence_backed": bool(events),
        }

    @staticmethod
    def _fulfillment_evidence(evidence: list[dict[str, Any]]) -> dict[str, Any]:
        events = []
        for item in evidence:
            if item.get("stage") != "fulfillment.tracking":
                continue
            receipt = item.get("receipt") or {}
            events.append({
                "state": receipt.get("state"),
                "state_name": receipt.get("state_name") or item.get("status"),
                "order_id": receipt.get("order_id"),
                "tracking_number": receipt.get("tracking_number"),
                "business_reference": receipt.get("business_reference"),
                "confirmed_delivery": receipt.get("is_confirmed_delivery"),
                "exception_reason": receipt.get("exception_reason"),
                "exception_code": receipt.get("exception_code"),
                "number_of_attempts": receipt.get("number_of_attempts"),
                "provider": receipt.get("provider"),
                "recorded_at": item.get("created_at"),
                "evidence_key": item.get("evidence_key"),
            })
        events.sort(key=lambda item: (item.get("recorded_at") or "", item.get("state") or 0))
        latest = events[-1] if events else None
        return {"status": latest.get("state_name") if latest else "not_available",
                "latest": latest, "events": events, "evidence_backed": bool(events)}

    @staticmethod
    def _learning(execution_key: str, outcome: dict[str, Any], payment: dict[str, Any], fulfillment: dict[str, Any]) -> dict[str, Any]:
        from app.services.evaluation_learning import EvaluationLearningService
        observed = []
        if payment.get("evidence_backed"):
            observed.append("payment_completed")
        if fulfillment.get("evidence_backed"):
            observed.append(fulfillment.get("status"))
        lifecycle = {
            "decision_id": execution_key, "capability_id": "commerce_golden_revenue",
            "state": "outcome_observed" if observed else "executed",
            "approval": {"status": "approved"},
            "execution": {"status": "completed" if outcome.get("id") else "unknown"},
            "observed_outcome": observed,
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
        }
        result = EvaluationLearningService.evaluate(lifecycle)
        return {"status": result.get("status"), "score": result.get("score"),
                "signals": [result.get("recommendation")] if result.get("recommendation") else [],
                "evaluation": result}

    @staticmethod
    def _payment_evidence(evidence: list[dict[str, Any]]) -> dict[str, Any]:
        events = []
        for item in evidence:
            if item.get("stage") != "payment.completed":
                continue
            receipt = item.get("receipt") or {}
            events.append({"payment_id": receipt.get("payment_id"), "amount": receipt.get("amount"),
                           "currency": receipt.get("currency"), "provider": receipt.get("provider"),
                           "provider_transaction_id": receipt.get("provider_transaction_id"),
                           "provider_order_id": receipt.get("provider_order_id"),
                           "recorded_at": item.get("created_at"), "evidence_key": item.get("evidence_key")})
        latest = events[-1] if events else None
        return {"status": "completed" if latest else "not_available", "latest": latest,
                "events": events, "evidence_backed": bool(events)}

    @classmethod
    def _roi(cls, data: dict[str, Any], evidence: list[dict[str, Any]] | None = None, revenue: dict[str, Any] | None = None) -> float | None:
        revenue = revenue or cls._recorded_revenue(0, data, evidence)
        cost = data.get("cost_amount")
        if not revenue or not revenue.get("evidence_backed") or cost is None or float(cost) <= 0:
            return None
        return round((revenue["amount"] - float(cost)) / float(cost), 6)


commercial_outcome_trace = CommercialOutcomeTraceService()
