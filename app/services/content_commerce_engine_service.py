"""Content-to-commerce engine for Kemet's profit-first operating loop.

Composes existing governed content, distribution, lead, revenue, fulfillment,
and profit evidence services without creating a separate SaaS business layer.
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from app.services.content_factory_service import content_factory_service
from app.services.revenue_pipeline_service import revenue_pipeline_service


class ContentCommerceEngineService:
    VERSION = "1.0"
    FUNNEL = (
        "content_factory",
        "distribution",
        "audience_leads",
        "offers",
        "revenue_pipeline",
        "fulfillment",
        "profit_intelligence",
    )

    @staticmethod
    def _org(value: Any) -> int:
        value = int(value or 0)
        if value <= 0:
            raise ValueError("organization_required")
        return value

    @staticmethod
    def _text(value: Any, error: str, limit: int = 500) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError(error)
        return value[:limit]

    @staticmethod
    def _pipeline_key(org: int, content_id: str, email: str, offer: str) -> str:
        raw = f"content-commerce:{org}:{content_id}:{email.lower()}:{offer}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]

    def build_plan(
        self,
        *,
        organization_id: int,
        title: str,
        premise: str,
        content_id: str,
        offer_name: str,
        audience: str = "Arabic-speaking audience",
        platforms: list[str] | None = None,
        quoted_amount: Any = 0,
    ) -> dict[str, Any]:
        org = self._org(organization_id)
        content_id = self._text(content_id, "content_id_required", 160)
        offer_name = self._text(offer_name, "offer_name_required", 255)
        package = content_factory_service.build(
            organization_id=org,
            title=self._text(title, "title_required", 200),
            premise=self._text(premise, "premise_required", 3000),
            audience=audience,
            platforms=platforms,
        )
        return {
            "success": True,
            "engine": "kemet_content_commerce_engine",
            "version": self.VERSION,
            "content_id": content_id,
            "funnel": list(self.FUNNEL),
            "content": package,
            "offer": {
                "name": offer_name,
                "quoted_amount": float(quoted_amount or 0),
                "currency": "EGP",
                "status": "ready_for_human_approval",
            },
            "commercial_gate": {
                "lead_capture": "enabled",
                "payment": "recorded_only_after_verified_payment",
                "fulfillment": "approval_required",
                "profit": "evidence_backed_only",
            },
            "governance": {
                "external_execution": False,
                "auto_publish": False,
                "auto_payment": False,
                "human_approval_required": True,
            },
        }
    def intake_lead(
        self,
        *,
        organization_id: int,
        content_id: str,
        offer_name: str,
        company_name: str,
        email: str,
        phone: str = "",
        message: str = "",
        source: str = "content_distribution",
        quoted_amount: Any = 0,
    ) -> dict[str, Any]:
        org = self._org(organization_id)
        content_id = self._text(content_id, "content_id_required", 160)
        offer_name = self._text(offer_name, "offer_name_required", 255)
        email = self._text(email, "customer_email_required", 320)
        pipeline_key = self._pipeline_key(org, content_id, email, offer_name)
        return revenue_pipeline_service.intake(
            organization_id=org,
            company_name=self._text(company_name, "company_name_required", 255),
            email=email,
            phone=phone,
            message=message,
            source=f"content:{content_id}:{source}"[:60],
            offer_name=offer_name,
            quoted_amount=quoted_amount,
            pipeline_key=pipeline_key,
        )

    def profit_intelligence(self, *, organization_id: int) -> dict[str, Any]:
        org = self._org(organization_id)
        dashboard = revenue_pipeline_service.dashboard(org)
        by_content: dict[str, dict[str, float]] = {}
        for row in dashboard.get("records", []):
            source = str(row.get("source") or "")
            if not source.startswith("content:"):
                continue
            parts = source.split(":", 2)
            content_id = parts[1] if len(parts) > 1 else "unknown"
            bucket = by_content.setdefault(content_id, {
                "paid_revenue": 0.0, "cost": 0.0, "profit": 0.0,
                "pipeline_count": 0.0, "won_count": 0.0,
            })
            bucket["paid_revenue"] += float(row.get("paid_amount") or 0)
            bucket["cost"] += float(row.get("costs", {}).get("total") or 0)
            if row.get("profit_status") == "verified":
                bucket["profit"] += float(row.get("profit") or 0)
            bucket["pipeline_count"] += 1
            if row.get("stage") in {"paid", "fulfillment", "delivered", "closed"}:
                bucket["won_count"] += 1
        for bucket in by_content.values():
            revenue = bucket["paid_revenue"]
            bucket["margin_pct"] = round((bucket["profit"] / revenue) * 100, 2) if revenue else None
        return {
            "success": True,
            "engine": "kemet_content_profit_intelligence",
            "version": self.VERSION,
            "organization_id": org,
            "funnel": list(self.FUNNEL),
            "portfolio": dashboard.get("financials", {}),
            "by_content": by_content,
            "evidence_policy": "verified_bound_payment_and_recorded_costs_only",
            "governance": {"read_only": True, "causal_claim": False, "external_execution": False},
        }


content_commerce_engine_service = ContentCommerceEngineService()
