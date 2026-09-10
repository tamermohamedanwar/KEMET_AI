from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256


@dataclass(frozen=True)
class NormalizedMessage:
    message_id: str
    channel: str
    external_message_id: str
    text: str
    language: str
    user_id: int | None = None
    organization_id: int | None = None
    conversation_id: int | None = None
    metadata: dict = field(default_factory=dict)
    received_at: str = ""


class OmnichannelGateway:
    VERSION = "1.0"
    CHANNELS = ("web", "whatsapp", "telegram")

    def normalize(self, *, channel, text, external_message_id="", user_id=None, organization_id=None, conversation_id=None, metadata=None):
        channel = str(channel or "").strip().lower()
        text = str(text or "").strip()
        if channel not in self.CHANNELS:
            raise ValueError("Unsupported channel")
        if not text:
            raise ValueError("Message text is required")
        key = f"{channel}|{external_message_id}|{text}".encode()
        return NormalizedMessage(sha256(key).hexdigest(), channel, str(external_message_id or ""), text,
                                 self.detect_language(text), user_id, organization_id, conversation_id,
                                 dict(metadata or {}), datetime.now(timezone.utc).isoformat())

    @staticmethod
    def detect_language(text):
        return "ar" if any("\u0600" <= char <= "\u06ff" for char in text) else "en"

    def route(self, message):
        return {"message_id": message.message_id, "channel": message.channel, "language": message.language,
                "organization_id": message.organization_id, "user_id": message.user_id,
                "conversation_id": message.conversation_id, "next": "kemet_core", "external_execution": False}

    def canonical_request(self, message):
        return {"request_id": message.message_id, "channel": message.channel, "language": message.language,
                "text": message.text, "user_id": message.user_id, "organization_id": message.organization_id,
                "conversation_id": message.conversation_id, "metadata": dict(message.metadata)}

    def response_envelope(self, message, *, content, requires_approval=False, executed=False):
        return {"gateway": "kemet_omnichannel_gateway", "version": self.VERSION, "message_id": message.message_id,
                "channel": message.channel, "language": message.language, "content": str(content),
                "requires_approval": bool(requires_approval), "executed": bool(executed),
                "governance": {"read_only": not executed, "advisory": not executed, "external_execution": False,
                               "database_mutation": False, "auto_execute": False,
                               "human_approval_required": bool(requires_approval)}}

    def health(self):
        return {"engine": "kemet_omnichannel_gateway", "version": self.VERSION, "status": "ok",
                "channels": list(self.CHANNELS),
                "governance": {"read_only": True, "advisory": True, "external_execution": False,
                               "database_mutation": False, "auto_execute": False}}


omnichannel_gateway = OmnichannelGateway()
