from __future__ import annotations

from typing import Any, Mapping

from app.services.revenue_identity_reconciliation_service import revenue_identity_reconciliation_service


class ContentRevenueAttributionService:
    """Read-only content-to-commerce measurement with conservative evidence rules."""

    VERSION = "1.0"

    @classmethod
    def evaluate(
        cls,
        *,
        content_id: str,
        metrics: Mapping[str, Any],
        payment_evidence: list[Mapping[str, Any]] | None = None,
        organization_id: int | None = None,
        publication_id: str = "",
        execution_key: str = "",
    ) -> dict[str, Any]:
        if not str(content_id or "").strip():
            raise ValueError("content_id_required")
        normalized = cls._metrics(metrics)
        evidence = cls._verified_payments(payment_evidence or [], content_id)
        reconciled_amount = None
        if payment_evidence and organization_id is not None and publication_id and execution_key:
            try:
                reconciliation = revenue_identity_reconciliation_service.reconcile(
                    organization_id=int(organization_id), content_id=str(content_id),
                    publication_id=str(publication_id), execution_key=str(execution_key),
                    evidence=list(payment_evidence),
                )
                if reconciliation.get("status") == "reconciled":
                    transactions = (reconciliation.get("identity") or {}).get("transactions") or []
                    reconciled_amount = sum(cls._nonnegative(tx.get("amount")) for tx in transactions)
                else:
                    evidence = []
            except (TypeError, ValueError):
                evidence = []
        revenue = round(reconciled_amount if reconciled_amount is not None else sum(item["amount"] for item in evidence), 4)
        qualified = normalized["qualified_views"]
        rpm = round((revenue / qualified) * 1000, 4) if qualified and evidence else None
        return {
            "success": True,
            "engine": "kemet_content_revenue_attribution",
            "version": cls.VERSION,
            "content_id": str(content_id),
            "revenue": {
                "amount": revenue,
                "currency": evidence[0]["currency"] if evidence else None,
                "verified_payment_count": len(evidence),
                "evidence_backed": bool(evidence),
            },
            "economics": {
                "revenue_per_1000_qualified_views": rpm,
                "qualified_views": qualified,
            },
            "attribution": {
                "level": "observational",
                "causal_claim": False,
                "roi_claim": False,
                "source": "payment_evidence" if evidence else "not_available",
            },
            "governance": {
                "read_only": True,
                "database_mutation": False,
                "external_execution": False,
                "execution_authority": False,
            },
        }

    @staticmethod
    def _nonnegative(value: Any) -> float:
        try:
            return max(0.0, float(value or 0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _metrics(metrics: Mapping[str, Any]) -> dict[str, float]:
        result = {}
        for key in ("qualified_views", "views", "conversions"):
            try:
                value = float(metrics.get(key, 0) or 0)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid_metric:{key}") from exc
            if value < 0:
                raise ValueError(f"negative_metric:{key}")
            result[key] = value
        return result

    @staticmethod
    def _verified_payments(
        evidence: list[Mapping[str, Any]], content_id: str
    ) -> list[dict[str, Any]]:
        verified = []
        for item in evidence:
            if item.get("stage") != "payment.completed":
                continue
            receipt = item.get("receipt") or {}
            if receipt.get("content_id") != content_id:
                continue
            if not receipt.get("provider_transaction_id"):
                continue
            try:
                amount = float(receipt.get("amount"))
            except (TypeError, ValueError):
                continue
            if amount < 0:
                continue
            verified.append(
                {
                    "payment_id": receipt.get("payment_id"),
                    "amount": amount,
                    "currency": receipt.get("currency"),
                    "provider_transaction_id": receipt["provider_transaction_id"],
                }
            )
        return verified


content_revenue_attribution_service = ContentRevenueAttributionService()
