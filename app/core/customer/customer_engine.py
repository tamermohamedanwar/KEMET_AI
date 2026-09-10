from typing import Any, Dict, List, Optional


class CustomerEngine:
    SUPPORTED_CHANNELS = {
        "web",
        "whatsapp",
        "telegram",
        "email",
        "phone",
        "api",
    }

    @staticmethod
    def normalize(
        customer_id: Any,
        channel: str = "web",
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        channel = str(channel or "web").strip().lower()
        message = str(message or "").strip()

        if not customer_id:
            return {
                "success": False,
                "status": "invalid",
                "error": "customer_id_required",
            }

        if channel not in CustomerEngine.SUPPORTED_CHANNELS:
            return {
                "success": False,
                "status": "invalid",
                "error": "unsupported_channel",
                "channel": channel,
            }

        if not message:
            return {
                "success": False,
                "status": "invalid",
                "error": "message_required",
            }

        return {
            "success": True,
            "status": "ready",
            "customer_id": str(customer_id),
            "channel": channel,
            "message": message,
            "metadata": metadata or {},
        }

    @staticmethod
    def build_customer_context(
        customer_id: Any,
        channel: str,
        message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = CustomerEngine.normalize(
            customer_id=customer_id,
            channel=channel,
            message=message,
            metadata=metadata,
        )

        if not normalized["success"]:
            return normalized

        return {
            "success": True,
            "engine": "kemet_customer",
            "version": "1.0",
            "customer": {
                "id": normalized["customer_id"],
            },
            "conversation": {
                "channel": normalized["channel"],
                "message": normalized["message"],
                "history": history or [],
            },
            "metadata": normalized["metadata"],
            "mode": "advisory",
            "external_execution": False,
        }

    @staticmethod
    def route_message(context: Dict[str, Any]) -> Dict[str, Any]:
        if not context.get("success"):
            return context

        channel = context["conversation"]["channel"]

        return {
            "success": True,
            "status": "ready",
            "engine": "kemet_omnichannel",
            "channel": channel,
            "customer_id": context["customer"]["id"],
            "requires_approval": channel in {"whatsapp", "telegram", "email", "phone"},
            "external_execution": False,
        }


def customer_context(**kwargs: Any) -> Dict[str, Any]:
    return CustomerEngine.build_customer_context(**kwargs)
