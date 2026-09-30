from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.services.content_commerce_engine_service import content_commerce_engine_service
from app.services.next_episode_learning_service import next_episode_learning_service
from app.services.revenue_pipeline_service import revenue_pipeline_service


class RevenueFirstCommercialCycleService:
    VERSION = "1.0"
    STAGES = (
        "verified_content",
        "verified_distribution",
        "cta_lead",
        "offer",
        "payment",
        "fulfillment",
        "profit",
        "learning",
    )

    @staticmethod
    def _required_text(value: Any, error: str, limit: int = 500) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError(error)
        return value[:limit]

    @staticmethod
    def _verified(flag: Any, error: str) -> None:
        if flag is not True:
            raise ValueError(error)

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def prepare(
        self,
        *,
        organization_id: int,
        content: Mapping[str, Any],
        distribution: Mapping[str, Any],
        offer: Mapping[str, Any],
    ) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not isinstance(content, Mapping):
            raise ValueError("content_required")
        if not isinstance(distribution, Mapping):
            raise ValueError("distribution_required")
        if not isinstance(offer, Mapping):
            raise ValueError("offer_required")

        content_id = self._required_text(content.get("content_id"), "content_id_required", 200)
        self._verified(content.get("verified"), "verified_content_required")
        self._verified(distribution.get("verified"), "verified_distribution_required")
        self._required_text(distribution.get("publication_id"), "distribution_publication_id_required", 255)

        channel = self._required_text(distribution.get("channel"), "distribution_channel_required", 80)
        publication_id = self._required_text(distribution.get("publication_id"), "distribution_publication_id_required", 255)
        cta = self._required_text(distribution.get("cta"), "cta_required", 1000)
        offer_name = self._required_text(offer.get("name"), "offer_name_required", 255)
        try:
            quoted_amount = float(offer.get("quoted_amount", 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_offer_amount") from exc
        if quoted_amount <= 0:
            raise ValueError("offer_amount_must_be_positive")
        currency = str(offer.get("currency") or "EGP").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("invalid_offer_currency")

        artifact_digest = self._required_text(content.get("artifact_digest"), "artifact_digest_required", 128)
        payload = {
            "organization_id": int(organization_id),
            "content_id": content_id,
            "artifact_digest": artifact_digest,
            "channel": channel,
            "publication_id": publication_id,
            "cta": cta,
            "offer": {
                "name": offer_name,
                "quoted_amount": quoted_amount,
                "currency": currency,
            },
        }
        return {
            "success": True,
            "status": "ready_for_lead",
            "version": self.VERSION,
            "stages": list(self.STAGES),
            "identity": {
                "organization_id": int(organization_id),
                "content_id": content_id,
                "cycle_digest": self._digest(payload),
            },
            "content": {
                "verified": True,
                "artifact_digest": content.get("artifact_digest"),
            },
            "distribution": {
                "verified": True,
                "channel": channel,
                "publication_id": distribution.get("publication_id"),
                "external_publication_executed": False,
            },
            "cta": {
                "text": cta,
                "lead_capture": True,
            },
            "offer": payload["offer"],
            "governance": {
                "external_execution": False,
                "auto_publish": False,
                "auto_payment": False,
                "human_approval_required": True,
                "canonical_executor": "kemet_canonical_runtime",
            },
        }
    def intake_lead(
        self,
        *,
        prepared: Mapping[str, Any],
        company_name: str,
        email: str,
        phone: str = "",
        message: str = "",
    ) -> dict[str, Any]:
        if not isinstance(prepared, Mapping) or prepared.get("success") is not True:
            raise ValueError("commercial_cycle_not_prepared")
        identity = prepared.get("identity") or {}
        offer = prepared.get("offer") or {}
        distribution = prepared.get("distribution") or {}
        return content_commerce_engine_service.intake_lead(
            organization_id=int(identity.get("organization_id") or 0),
            content_id=str(identity.get("content_id") or ""),
            offer_name=str(offer.get("name") or ""),
            company_name=company_name,
            email=email,
            phone=phone,
            message=message,
            source=f"verified_distribution:{distribution.get('channel')}",
            quoted_amount=offer.get("quoted_amount", 0),
        )

    def advance(self, *, organization_id: int, pipeline_key: str, stage: str) -> dict[str, Any]:
        """Advance an existing tenant-scoped commercial cycle through the governed pipeline."""
        return revenue_pipeline_service.advance(
            organization_id=int(organization_id), pipeline_key=str(pipeline_key), stage=str(stage)
        )

    def record_payment(self, *, organization_id: int, pipeline_key: str, payment_id: int) -> dict[str, Any]:
        """Bind only a completed payment record; payment execution remains external and governed."""
        return revenue_pipeline_service.attach_payment(
            organization_id=int(organization_id), pipeline_key=str(pipeline_key), payment_id=int(payment_id)
        )

    def record_cost(self, *, organization_id: int, pipeline_key: str, category: str, amount: Any) -> dict[str, Any]:
        return revenue_pipeline_service.record_cost(
            organization_id=int(organization_id), pipeline_key=str(pipeline_key), category=str(category), amount=amount
        )

    def fulfill(self, *, organization_id: int, pipeline_key: str, fulfillment_reference: str) -> dict[str, Any]:
        """Record fulfillment only after the pipeline has verified payment."""
        return revenue_pipeline_service.attach_delivery(
            organization_id=int(organization_id), pipeline_key=str(pipeline_key),
            fulfillment_reference=str(fulfillment_reference)
        )

    def close(self, *, organization_id: int, pipeline_key: str) -> dict[str, Any]:
        return revenue_pipeline_service.close(
            organization_id=int(organization_id), pipeline_key=str(pipeline_key)
        )

    def learning(
        self,
        *,
        organization_id: int,
        episode: Mapping[str, Any],
        observed: Mapping[str, Any],
    ) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        return next_episode_learning_service.build_recommendation(
            organization_id=int(organization_id),
            episode=episode,
            observed=observed,
        )

    def status(self, *, organization_id: int) -> dict[str, Any]:
        result = content_commerce_engine_service.profit_intelligence(
            organization_id=int(organization_id)
        )
        return {
            "success": True,
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "stages": list(self.STAGES),
            "profit": result,
            "governance": {
                "read_only": True,
                "external_execution": False,
                "auto_publish": False,
                "auto_payment": False,
                "human_approval_required": True,
            },
        }


revenue_first_commercial_cycle_service = RevenueFirstCommercialCycleService()
