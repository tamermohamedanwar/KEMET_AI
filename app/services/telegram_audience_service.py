from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


class TelegramAudienceService:
    VERSION = "1.0"
    SCHEMA = "kemet.telegram_audience.v1"

    def build_funnel(self, *, organization_id: int, channel_ref: str,
                     bot_ref: str | None = None, content_id: str | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not str(channel_ref or "").strip():
            raise ValueError("channel_ref_required")
        funnel = {
            "schema": self.SCHEMA, "version": self.VERSION,
            "organization_id": int(organization_id),
            "channel_ref": str(channel_ref)[:200],
            "bot_ref": str(bot_ref)[:200] if bot_ref else None,
            "content_id": str(content_id)[:200] if content_id else None,
            "flow": ["DISCOVER", "JOIN", "WELCOME", "CONTINUE_STORY", "VOTE",
                     "PREMIUM_OFFER", "PAY", "MEASURE"],
            "value_ladder": {
                "free": ["stories", "trailers", "votes"],
                "premium": ["extended_story", "behind_the_scenes", "early_access"],
                "commerce": ["official_digital_products", "services"],
            },
            "payment": {"provider": "telegram_stars", "execution_ready": False,
                        "approval_required": True, "official_api_only": True},
            "measurement": ["joins", "active_members", "story_continuation_clicks",
                            "premium_interest", "paid_unlocks", "revenue"],
            "audience_ownership": True,
            "auto_message_execution": False,
            "execution_authority": False,
            "human_approval_required": True,
            "governance": {"read_only": True, "canonical_executor": "kemet_canonical_runtime"},
        }
        funnel["funnel_digest"] = self._digest(funnel)
        return funnel

    def build_cta(self, *, experiment_id: str, destination: str = "telegram") -> dict[str, Any]:
        if not str(experiment_id or "").strip():
            raise ValueError("experiment_id_required")
        if destination != "telegram":
            raise ValueError("unsupported_destination")
        return {
            "schema": "kemet.telegram_cta.v1",
            "experiment_id": str(experiment_id),
            "destination": "telegram",
            "cta": "Continue the story and vote on what happens next.",
            "tracking": {"experiment_id": str(experiment_id), "attribution_required": True},
            "external_execution": False, "approval_required": True,
        }

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode()).hexdigest()


telegram_audience_service = TelegramAudienceService()
