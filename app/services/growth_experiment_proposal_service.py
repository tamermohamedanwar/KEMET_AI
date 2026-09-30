from __future__ import annotations

from typing import Any, Mapping


class GrowthExperimentProposalService:
    """Creates review-only growth experiment proposals from verified revenue signals."""

    VERSION = "1.0"

    @classmethod
    def propose(cls, *, organization_id: int, portfolio: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        source = portfolio or {}
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for record in source.get("records") or []:
            if not isinstance(record, Mapping):
                continue
            if record.get("eligible") is not True:
                continue
            if not all(str(record.get(key) or "").strip() for key in ("content_id", "publication_id", "execution_key", "channel")):
                continue
            grouped.setdefault(str(record.get("channel")).strip().lower(), []).append(record)
        rows = []
        for channel, records in grouped.items():
            revenue = sum(cls._nonnegative(record.get("verified_revenue")) for record in records)
            bindings = [
                {
                    "content_id": str(record.get("content_id")),
                    "publication_id": str(record.get("publication_id")),
                    "execution_key": str(record.get("execution_key")),
                    "metric_evidence_digest": str(record.get("metric_evidence_digest") or ""),
                }
                for record in records
            ]
            views = 0.0
            for record in records:
                views += cls._nonnegative(record.get("qualified_views"))
            rpm = (revenue / views) * 1000 if views else None
            rows.append({
                "channel": channel,
                "basis": {
                    "verified_revenue": revenue,
                    "qualified_views": views,
                    "reconciled_content_count": len(records),
                    "revenue_per_1000_qualified_views": round(rpm, 4) if rpm is not None else None,
                    "evidence_bindings": bindings,
                },
                "proposal": {
                    "type": "controlled_growth_experiment",
                    "objective": "validate_repeatable_distribution_or_content_signal",
                    "scope": "review_required",
                    "success_metric": "incremental_verified_revenue",
                    "guardrail": "do_not_treat_unverified_attribution_as_revenue",
                },
            })
        return {
            "success": True,
            "engine": "kemet_growth_experiment_proposal",
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "proposals": rows,
            "approval": {
                "status": "pending_human_review" if rows else "no_proposal",
                "required": True,
                "execution_allowed": False,
            },
            "governance": {
                "read_only": True,
                "tenant_scoped": True,
                "database_mutation": False,
                "external_execution": False,
                "execution_authority": False,
                "financial_action": False,
                "causal_claim": False,
                "roi_claim": False,
            },
        }

    @staticmethod
    def _nonnegative(value: Any) -> float:
        try:
            return max(0.0, float(value or 0))
        except (TypeError, ValueError):
            return 0.0


growth_experiment_proposal_service = GrowthExperimentProposalService()
