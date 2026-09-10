from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ChannelMessage:
    channel: str
    external_user_id: str
    text: str
    organization_id: Optional[int] = None
    user_id: Optional[int] = None
    conversation_id: Optional[int] = None
    language: str = "en"


class OmnichannelService:
    VERSION = "1.0"
    CHANNELS = ("web", "whatsapp", "telegram")

    @staticmethod
    def detect_language(text: str) -> str:
        arabic = sum("\u0600" <= char <= "\u06ff" for char in text or "")
        latin = sum(("a" <= char.lower() <= "z") for char in text or "")
        return "ar" if arabic > latin else "en"

    def normalize(self, channel, external_user_id, text, **context):
        channel = str(channel or "").strip().lower()
        external_user_id = str(external_user_id or "").strip()
        text = str(text or "").strip()
        if channel not in self.CHANNELS:
            raise ValueError("Unsupported channel")
        if not external_user_id or not text:
            raise ValueError("Message identity and text are required")
        return ChannelMessage(
            channel=channel,
            external_user_id=external_user_id,
            text=text,
            organization_id=context.get("organization_id"),
            user_id=context.get("user_id"),
            conversation_id=context.get("conversation_id"),
            language=self.detect_language(text),
        )

    def route(self, message: ChannelMessage) -> dict:
        return {
            "channel": message.channel,
            "language": message.language,
            "identity": {
                "external_user_id": message.external_user_id,
                "user_id": message.user_id,
                "organization_id": message.organization_id,
                "conversation_id": message.conversation_id,
            },
            "next": "kemet_core",
            "governance": {
                "read_only": True,
                "advisory": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
                "human_approval_required": True,
            },
        }


omnichannel_service = OmnichannelService()
