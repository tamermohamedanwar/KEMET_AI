from __future__ import annotations

from typing import Any, Mapping

from app.models.payment import Payment


class RevenueIdentityReconciliationService:
    """Read-only reconciliation of content, publication, execution, and paid transaction identity."""

    VERSION = "1.0"

    @classmethod
    def reconcile(
        cls,
        *,
        organization_id: int,
        content_id: str,
        publication_id: str,
        execution_key: str,
        evidence: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        if not str(content_id or "").strip():
            raise ValueError("content_id_required")
        if not str(publication_id or "").strip():
            raise ValueError("publication_id_required")
        if not str(execution_key or "").strip():
            raise ValueError("execution_key_required")

        candidates = []
        for item in evidence or []:
            if not isinstance(item, Mapping) or item.get("stage") != "payment.completed":
                continue
            receipt = item.get("receipt") or {}
            candidate_content = str(item.get("content_id") or receipt.get("content_id") or "")
            candidate_publication = str(item.get("publication_id") or receipt.get("publication_id") or "")
            transaction_id = str(item.get("provider_transaction_id") or receipt.get("provider_transaction_id") or "").strip()
            evidence_execution_key = str(item.get("execution_key") or receipt.get("execution_key") or "").strip()
            evidence_organization_id = item.get("organization_id", receipt.get("organization_id"))
            if evidence_execution_key and evidence_execution_key != str(execution_key):
                continue
            if evidence_organization_id is not None and int(evidence_organization_id) != int(organization_id):
                continue
            if candidate_content != content_id or candidate_publication not in {"", publication_id} or not transaction_id:
                continue
            try:
                payment_id = int(receipt.get("payment_id")) if receipt.get("payment_id") is not None else None
            except (TypeError, ValueError):
                payment_id = None
            payment = None
            if payment_id is not None:
                payment = Payment.query.filter_by(
                    id=payment_id, organization_id=int(organization_id), status="paid"
                ).first()
            if payment is None:
                continue
            if str(payment.provider_transaction_id or "") != transaction_id:
                continue
            candidates.append({
                "payment_id": payment.id,
                "provider": payment.provider,
                "provider_transaction_id": transaction_id,
                "provider_order_id": payment.provider_order_id,
                "amount": float(payment.amount),
                "currency": payment.currency,
                "status": payment.status,
            })

        unique = {item["provider_transaction_id"]: item for item in candidates}
        verified = list(unique.values())
        status = "reconciled" if verified else "not_reconciled"
        return {
            "success": True,
            "status": status,
            "engine": "kemet_revenue_identity_reconciliation",
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "identity": {
                "content_id": str(content_id),
                "publication_id": str(publication_id),
                "execution_key": str(execution_key),
                "payment_count": len(verified),
                "transactions": verified,
            },
            "evidence": {
                "source": "payment.completed_execution_evidence_and_paid_payment_record",
                "verified": bool(verified),
                "fail_closed": True,
            },
            "governance": {
                "read_only": True,
                "tenant_scoped": True,
                "database_mutation": False,
                "external_execution": False,
                "execution_authority": False,
                "human_approval_required_for_actions": True,
            },
        }


revenue_identity_reconciliation_service = RevenueIdentityReconciliationService()
