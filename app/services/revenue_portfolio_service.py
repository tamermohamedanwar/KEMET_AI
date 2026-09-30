from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from app.services.revenue_identity_reconciliation_service import revenue_identity_reconciliation_service


class RevenuePortfolioService:
    """Read-only portfolio aggregation over reconciled content revenue."""

    VERSION = "1.0"

    @classmethod
    def aggregate(cls, *, organization_id: int, content_results: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        total = 0.0
        qualified = 0.0
        reconciled_count = 0
        measured_count = 0
        channels: dict[str, dict[str, float]] = defaultdict(lambda: {"revenue": 0.0, "qualified_views": 0.0, "content_count": 0.0})
        records = []
        for item in content_results or []:
            if not isinstance(item, Mapping) or int(item.get("organization_id") or organization_id) != int(organization_id):
                continue
            reconciliation = item.get("reconciliation") or {}
            reconciled = reconciliation.get("status") == "reconciled"
            provider = item.get("provider_measurement") or {}
            measured = provider.get("verified") is True
            channel = str((item.get("publication") or {}).get("channel") or item.get("channel") or "")
            identity = reconciliation.get("identity") or {}
            identity_content = str(identity.get("content_id") or item.get("content_id") or "")
            identity_publication = str(identity.get("publication_id") or (item.get("publication") or {}).get("publication_id") or "")
            identity_execution = str(identity.get("execution_key") or item.get("execution_key") or "")
            metric_evidence_digest = str(provider.get("metric_evidence_digest") or "").strip()
            payment_evidence = item.get("payment_evidence") or item.get("evidence") or []
            reconciled_amount = None
            if payment_evidence:
                try:
                    verified_identity = revenue_identity_reconciliation_service.reconcile(
                        organization_id=int(organization_id),
                        content_id=identity_content,
                        publication_id=identity_publication,
                        execution_key=identity_execution,
                        evidence=list(payment_evidence),
                    )
                    reconciled = verified_identity.get("status") == "reconciled"
                    transactions = (verified_identity.get("identity") or {}).get("transactions") or []
                    if reconciled:
                        reconciled_amount = sum(cls._nonnegative(tx.get("amount")) for tx in transactions)
                except (TypeError, ValueError):
                    reconciled = False
            eligible = reconciled and measured and bool(identity_content and identity_publication and identity_execution and metric_evidence_digest)
            claimed_revenue = cls._nonnegative(((item.get("commercial") or {}).get("revenue") or {}).get("amount"))
            revenue = (reconciled_amount if reconciled_amount is not None else claimed_revenue) if eligible else 0.0
            economics = (item.get("commercial") or {}).get("economics") or {}
            qv = cls._nonnegative(economics.get("qualified_views")) if eligible else 0.0
            if eligible:
                total += revenue
                qualified += qv
                reconciled_count += 1
                channels[channel]["revenue"] += revenue
                channels[channel]["qualified_views"] += qv
                channels[channel]["content_count"] += 1
            if measured:
                measured_count += 1
            records.append({
                "content_id": identity_content,
                "publication_id": identity_publication,
                "execution_key": identity_execution,
                "channel": channel,
                "reconciled": reconciled,
                "measured": measured,
                "eligible": eligible,
                "metric_evidence_digest": metric_evidence_digest,
                "verified_revenue": round(revenue, 4) if eligible else None,
                "revenue_amount_source": "reconciled_payment_transactions" if reconciled_amount is not None and eligible else ("reconciled_content_evidence" if eligible else "none"),
                "qualified_views": qv if eligible else None,
            })
        channel_rows = []
        for channel, data in channels.items():
            rpm = (data["revenue"] / data["qualified_views"] * 1000) if data["qualified_views"] else None
            share = (data["revenue"] / total) if total else None
            channel_rows.append({
                "channel": channel,
                "verified_revenue": round(data["revenue"], 4),
                "qualified_views": data["qualified_views"],
                "reconciled_content_count": int(data["content_count"]),
                "revenue_per_1000_qualified_views": round(rpm, 4) if rpm is not None else None,
                "revenue_share": round(share, 6) if share is not None else None,
            })
        return {
            "success": True,
            "engine": "kemet_revenue_portfolio",
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "portfolio": {
                "verified_revenue": round(total, 4),
                "qualified_views": qualified,
                "reconciled_content_count": reconciled_count,
                "authoritatively_measured_content_count": measured_count,
                "revenue_per_1000_qualified_views": round(total / qualified * 1000, 4) if qualified else None,
            },
            "channels": channel_rows,
            "records": records,
            "decision_support": {
                "basis": "reconciled_payment_identity_and_authoritative_measurement",
                "proposal_mode": "human_review_only",
                "automatic_action": False,
                "financial_action": False,
                "external_action": False,
                "causal_claim": False,
                "roi_claim": False,
            },
            "governance": {
                "read_only": True, "tenant_scoped": True, "database_mutation": False,
                "external_execution": False, "execution_authority": False,
                "human_approval_required_for_actions": True,
            },
        }

    @staticmethod
    def _nonnegative(value: Any) -> float:
        try:
            return max(0.0, float(value or 0))
        except (TypeError, ValueError):
            return 0.0


revenue_portfolio_service = RevenuePortfolioService()
