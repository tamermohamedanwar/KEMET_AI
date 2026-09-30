from __future__ import annotations

from typing import Any, Mapping

from app.services.revenue_identity_reconciliation_service import revenue_identity_reconciliation_service


class RevenueCenterEvidenceService:
    """Read-only evidence aggregation for the Revenue Center."""

    VERSION = "1.0"

    @classmethod
    def summarize(
        cls,
        organization_id: int,
        content_results: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")

        records = []
        verified_revenue = 0.0
        verified_count = 0
        measured_count = 0

        for item in content_results or []:
            if not isinstance(item, Mapping):
                continue
            if int(item.get("organization_id") or organization_id) != int(organization_id):
                continue
            commercial = item.get("commercial") or {}
            revenue = commercial.get("revenue") or {}
            amount = cls._amount(revenue.get("amount"))
            evidence_backed = revenue.get("evidence_backed") is True
            publication = item.get("publication") or {}
            content_id = str(item.get("content_id") or "")
            publication_id = str(publication.get("publication_id") or "")
            execution_key = str(item.get("execution_key") or "")
            payment_evidence = item.get("payment_evidence") or item.get("evidence") or []
            if payment_evidence:
                try:
                    reconciliation = revenue_identity_reconciliation_service.reconcile(
                        organization_id=int(organization_id), content_id=content_id,
                        publication_id=publication_id, execution_key=execution_key,
                        evidence=list(payment_evidence),
                    )
                    if reconciliation.get("status") == "reconciled":
                        transactions = (reconciliation.get("identity") or {}).get("transactions") or []
                        amount = round(sum(cls._amount(tx.get("amount")) for tx in transactions), 4)
                        evidence_backed = bool(transactions)
                    else:
                        amount = 0.0
                        evidence_backed = False
                except (TypeError, ValueError):
                    amount = 0.0
                    evidence_backed = False
            provider = item.get("provider_measurement") or {}
            verified_measurement = provider.get("verified") is True
            if verified_measurement:
                measured_count += 1
            if evidence_backed:
                verified_revenue += amount
                verified_count += 1
            records.append({
                "content_id": str(item.get("content_id") or ""),
                "publication_id": publication_id,
                "channel": str((item.get("publication") or {}).get("channel") or ""),
                "verified_measurement": verified_measurement,
                "verified_revenue": evidence_backed,
                "revenue_amount": amount if evidence_backed else None,
                "currency": revenue.get("currency") if evidence_backed else None,
                "evidence_digest": (item.get("publication") or {}).get("evidence_digest"),
            })

        return {
            "success": True,
            "engine": "kemet_revenue_center_evidence",
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "verified_content_revenue": round(verified_revenue, 4),
            "verified_content_count": verified_count,
            "authoritatively_measured_content_count": measured_count,
            "records": records,
            "measurement": {
                "revenue_source": "verified_payment_evidence",
                "platform_source": "authoritative_provider_measurement",
                "forecast_is_not_recorded_revenue": True,
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
    def _amount(value: Any) -> float:
        try:
            value = float(value or 0)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, value)


revenue_center_evidence_service = RevenueCenterEvidenceService()
