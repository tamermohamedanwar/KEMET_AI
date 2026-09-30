from dataclasses import dataclass
from typing import Any, Mapping

from app.services.omnichannel_gateway import omnichannel_gateway


@dataclass(frozen=True)
class ChannelEnvelope:
    channel: str
    provider: str
    external_message_id: str
    external_user_id: str
    text: str
    organization_id: int
    metadata: dict[str, Any]


class ChannelAdapterService:
    VERSION = "1.0"
    CHANNELS = ("web", "whatsapp", "telegram")
    PROVIDERS = {"web": "kemet_web", "whatsapp": "provider_neutral", "telegram": "provider_neutral"}

    def ingest(self, *, channel: str, organization_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        channel = str(channel or "").strip().lower()
        if channel not in self.CHANNELS:
            raise ValueError("unsupported_channel")
        if not organization_id:
            raise ValueError("organization_id_required")
        external_message_id = str(payload.get("external_message_id") or payload.get("message_id") or "").strip()
        external_user_id = str(payload.get("external_user_id") or payload.get("user_id") or "").strip()
        text = str(payload.get("text") or payload.get("message") or "").strip()
        if not external_message_id:
            raise ValueError("external_message_id_required")
        if not external_user_id:
            raise ValueError("external_user_id_required")
        if not text:
            raise ValueError("message_text_required")
        message = omnichannel_gateway.normalize(
            channel=channel,
            text=text,
            external_message_id=external_message_id,
            organization_id=int(organization_id),
            conversation_id=payload.get("conversation_id"),
            metadata={"provider": self.PROVIDERS[channel], "external_user_id": external_user_id, **dict(payload.get("metadata") or {})},
        )
        return {
            "success": True,
            "engine": "kemet_channel_adapter",
            "version": self.VERSION,
            "envelope": ChannelEnvelope(channel, self.PROVIDERS[channel], external_message_id, external_user_id, text, int(organization_id), dict(payload.get("metadata") or {})).__dict__,
            "request": omnichannel_gateway.canonical_request(message),
            "route": omnichannel_gateway.route(message),
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
                "human_approval_required": True,
            },
        }

    def response_plan(self, *, channel: str, organization_id: int, content: str, requires_approval: bool = False) -> dict[str, Any]:
        channel = str(channel or "").strip().lower()
        if channel not in self.CHANNELS:
            raise ValueError("unsupported_channel")
        if not organization_id:
            raise ValueError("organization_id_required")
        if not str(content or "").strip():
            raise ValueError("response_content_required")
        return {
            "success": True,
            "channel": channel,
            "organization_id": int(organization_id),
            "delivery": "proposal_only",
            "provider": self.PROVIDERS[channel],
            "content": str(content).strip(),
            "requires_approval": bool(requires_approval),
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
                "human_approval_required": bool(requires_approval),
            },
        }


channel_adapter_service = ChannelAdapterService()
