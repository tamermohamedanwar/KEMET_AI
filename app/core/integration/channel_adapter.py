from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.omnichannel_gateway import NormalizedMessage, omnichannel_gateway


@dataclass(frozen=True)
class ChannelAdapter:
    """Provider-neutral channel boundary; never performs external I/O."""

    channel: str
    connector_id: str

    def inbound(self, *, text: str, external_message_id: str = "", user_id: int | None = None,
                organization_id: int | None = None, conversation_id: int | None = None,
                metadata: dict[str, Any] | None = None) -> NormalizedMessage:
        return omnichannel_gateway.normalize(
            channel=self.channel,
            text=text,
            external_message_id=external_message_id,
            user_id=user_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
            metadata=metadata,
        )

    def response_plan(self, message: NormalizedMessage, *, content: str,
                      requires_approval: bool = False) -> dict[str, Any]:
        return omnichannel_gateway.response_envelope(
            message,
            content=content,
            requires_approval=requires_approval,
            executed=False,
        )


CHANNEL_ADAPTERS = {
    "web": ChannelAdapter("web", "web"),
    "whatsapp": ChannelAdapter("whatsapp", "whatsapp"),
    "telegram": ChannelAdapter("telegram", "telegram"),
}


def get_channel_adapter(channel: str) -> ChannelAdapter:
    key = str(channel or "").strip().lower()
    try:
        return CHANNEL_ADAPTERS[key]
    except KeyError as exc:
        raise ValueError("Unsupported channel") from exc
