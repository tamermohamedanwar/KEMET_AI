from __future__ import annotations

from typing import Any, Mapping

from app.services.revenue_identity_reconciliation_service import revenue_identity_reconciliation_service


class RevenueContentDecisionSignalService:
    """Read-only commercial signals; never executes or ranks a business action automatically."""

    VERSION = "1.0"

    @classmethod
    def build(cls, *, organization_id: int, intelligence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        source = intelligence or {}
        records = []
        total_revenue = 0.0
        total_qualified_views = 0.0
        reviewable_count = 0
        measured_count = 0
        for item in source.get("records") or []:
            if not isinstance(item, Mapping):
                continue
            content_id = str(item.get("content_id") or "").strip()
            channel = str(item.get("channel") or "").strip().lower()
            publication_id = str(item.get("publication_id") or "").strip()
            execution_key = str(item.get("execution_key") or "").strip()
            supplied_reconciliation = (item.get("reconciliation") or {}).get("status") == "reconciled"
            payment_evidence = item.get("payment_evidence") or item.get("evidence") or []
            reconciled_amount = None
            if payment_evidence:
                try:
                    reconciliation = revenue_identity_reconciliation_service.reconcile(
                        organization_id=int(organization_id),
                        content_id=content_id,
                        publication_id=publication_id,
                        execution_key=execution_key,
                        evidence=list(payment_evidence),
                    )
                    reconciled = reconciliation.get("status") == "reconciled"
                    transactions = (reconciliation.get("identity") or {}).get("transactions") or []
                    if reconciled:
                        reconciled_amount = sum(cls._nonnegative(tx.get("amount")) for tx in transactions)
                except (TypeError, ValueError):
                    reconciled = False
            else:
                reconciled = supplied_reconciliation
            identity_complete = bool(content_id and channel and publication_id and execution_key)
            measured = item.get("verified_measurement") is True
            reviewable = reconciled and measured and identity_complete
            revenue = (reconciled_amount if reconciled_amount is not None else cls._nonnegative(item.get("verified_revenue_amount"))) if reviewable else 0.0
            qualified = cls._nonnegative(item.get("qualified_views")) if reviewable else 0.0
            rpm = (revenue / qualified) * 1000 if qualified else None
            readiness = "reviewable" if reviewable else "evidence_incomplete"
            if measured:
                measured_count += 1
            if reviewable:
                reviewable_count += 1
                total_revenue += revenue
                total_qualified_views += qualified
            records.append({
                "content_id": content_id,
                "channel": channel,
                "publication_id": publication_id,
                "execution_key": execution_key,
                "reconciliation_status": "reconciled" if reconciled else "not_reconciled",
                "decision_readiness": readiness,
                "identity_complete": identity_complete,
                "verified_revenue": round(revenue, 4) if reviewable else None,
                "qualified_views": qualified if reviewable else None,
                "revenue_per_1000_qualified_views": round(rpm, 4) if rpm is not None else None,
            })
        return {
            "success": True,
            "engine": "kemet_revenue_decision_signals",
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "signals": {
                "verified_revenue": round(total_revenue, 4),
                "verified_content_count": reviewable_count,
                "authoritatively_measured_content_count": measured_count,
                "revenue_per_1000_qualified_views": round((total_revenue / total_qualified_views) * 1000, 4) if total_qualified_views else None,
                "forecast_is_not_recorded_revenue": True,
            },
            "records": records,
            "decision_support": {
                "basis": "reconciled_payment_identity_plus_authoritative_measurement",
                "available_decision_types": ["review_distribution", "review_content", "review_conversion_evidence"],
                "automatic_action": False,
                "financial_action": False,
                "external_action": False,
                "causal_claim": False,
                "roi_claim": False,
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

    @staticmethod
    def _nonnegative(value: Any) -> float:
        try:
            return max(0.0, float(value or 0))
        except (TypeError, ValueError):
            return 0.0


revenue_content_decision_signal_service = RevenueContentDecisionSignalService()
