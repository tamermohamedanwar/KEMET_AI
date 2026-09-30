from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True)
class CampaignPlanRequest:
    organization_id: int
    campaign_id: str
    objective: str
    audience: str
    platforms: tuple[str, ...]
    budget_currency: str = "EGP"
    budget_amount: float | None = None
    geography: str = "Egypt"
    age_range: str = ""
    creative_ids: tuple[str, ...] = ()


class CampaignGovernanceService:
    VERSION = "1.0"
    PLATFORMS = ("facebook", "instagram", "youtube", "tiktok")
    OBJECTIVES = ("awareness", "traffic", "leads", "sales", "engagement")

    def plan(self, request: CampaignPlanRequest) -> dict[str, Any]:
        if request.organization_id <= 0:
            return self._blocked("organization_required")
        if not request.campaign_id.strip():
            return self._blocked("campaign_id_required")
        if request.objective not in self.OBJECTIVES:
            return self._blocked("unsupported_campaign_objective")
        if not request.audience.strip():
            return self._blocked("audience_required")
        platforms = tuple(dict.fromkeys(x.strip().lower() for x in request.platforms if x.strip()))
        if not platforms or any(x not in self.PLATFORMS for x in platforms):
            return self._blocked("unsupported_campaign_platform")
        if request.budget_amount is not None and request.budget_amount < 0:
            return self._blocked("budget_must_be_non_negative")
        payload = {
            "schema": "kemet.campaign_plan.v1",
            "version": self.VERSION,
            "organization_id": request.organization_id,
            "campaign_id": request.campaign_id.strip(),
            "objective": request.objective,
            "audience": request.audience.strip(),
            "geography": request.geography.strip() or "Egypt",
            "age_range": request.age_range.strip(),
            "platforms": list(platforms),
            "budget": {
                "currency": request.budget_currency.strip().upper() or "EGP",
                "amount": request.budget_amount,
                "status": "proposed" if request.budget_amount is not None else "not_set",
            },
            "creative_ids": list(request.creative_ids),
            "targeting": {
                "mode": "platform_native_targeting",
                "optimization": "platform_authoritative_delivery",
                "no_inferred_sensitive_attributes": True,
            },
            "measurement": {
                "required": True,
                "events": ["delivery", "reach", "qualified_views", "clicks", "leads", "conversion"],
                "revenue": "authoritative_payment_or_provider_evidence_only",
            },
            "governance": {
                "status": "review_required",
                "read_only": True,
                "external_execution": False,
                "execution_authority": False,
                "human_approval_required": True,
                "canonical_runtime_only": True,
                "no_autonomous_budget_spend": True,
                "no_sensitive_targeting_inference": True,
            },
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        payload["plan_digest"] = sha256(canonical.encode("utf-8")).hexdigest()
        return {"success": True, "status": "planned", "plan": payload}

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": "blocked",
            "error": error,
            "executed": False,
            "external_execution": False,
            "execution_authority": False,
        }


campaign_governance_service = CampaignGovernanceService()
