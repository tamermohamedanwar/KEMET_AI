import hashlib
import hmac
import os
import re
from typing import Any, Mapping


class ChannelWebhookService:
    VERSION = "1.0"

    @staticmethod
    def _secret(name: str) -> str:
        return os.getenv(name, "").strip()

    @staticmethod
    def verify_telegram(*, secret_token: str) -> bool:
        expected = ChannelWebhookService._secret("KEMET_TELEGRAM_WEBHOOK_SECRET")
        if not expected or not secret_token:
            return False
        return hmac.compare_digest(secret_token, expected)

    @staticmethod
    def verify_meta_signature(*, raw_body: bytes, signature: str,
                              organization_id: int | None = None) -> bool:
        secret = ChannelWebhookService._secret("KEMET_META_APP_SECRET")
        if not secret and organization_id:
            try:
                from app.core.secret_boundary import resolve_secret
                secret = resolve_secret(
                    "meta_whatsapp_cloud_api", "app_secret",
                    organization_id=int(organization_id),
                )
            except (RuntimeError, ValueError):
                secret = ""
        signature = str(signature or "").strip()
        if not secret or not signature.startswith("sha256="):
            return False
        supplied = signature.split("=", 1)[1]
        digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(supplied, digest)

    @staticmethod
    def verify_meta_challenge(*, verify_token: str, challenge: str) -> bool:
        expected = ChannelWebhookService._secret("KEMET_META_VERIFY_TOKEN")
        if not expected or not verify_token:
            return False
        return hmac.compare_digest(verify_token, expected) and bool(challenge)

    @staticmethod
    def extract_telegram(payload: Mapping[str, Any]) -> dict[str, Any]:
        callback = payload.get("callback_query") or {}
        if callback:
            sender = callback.get("from") or {}
            message = callback.get("message") or {}
            chat = message.get("chat") or {}
            callback_data = str(callback.get("data") or "").strip()
            return {
                "external_message_id": str(callback.get("id") or message.get("message_id") or ""),
                "external_user_id": str(sender.get("id") or ""),
                "conversation_id": str(chat.get("id") or ""),
                "text": callback_data,
                "metadata": {
                    "chat_type": chat.get("type"),
                    "username": sender.get("username"),
                    "telegram_update_kind": "callback_query",
                "telegram_update_id": payload.get("update_id"),
                    "callback_query_id": str(callback.get("id") or ""),
                    "callback_message_id": str(message.get("message_id") or ""),
                    "callback_data": callback_data,
                },
            }
        message = payload.get("message") or payload.get("edited_message") or {}
        sender = message.get("from") or {}
        chat = message.get("chat") or {}
        document = message.get("document") or {}
        return {
            "external_message_id": str(message.get("message_id") or ""),
            "external_user_id": str(sender.get("id") or ""),
            "conversation_id": str(chat.get("id") or ""),
            "text": str(message.get("text") or "").strip() or str(document.get("file_name") or ""),
            "metadata": {
                "chat_type": chat.get("type"),
                "username": sender.get("username"),
                "telegram_update_kind": "document" if document else "message",
            "telegram_update_id": payload.get("update_id"),
                "document_file_id": str(document.get("file_id") or ""),
                "document_file_name": str(document.get("file_name") or ""),
                "document_mime_type": str(document.get("mime_type") or ""),
                "document_file_size": document.get("file_size"),
            },
        }

    @staticmethod
    def extract_commercial_identity(text: str) -> dict[str, str]:
        """Extract only explicitly supplied commercial identity; never infer missing fields."""
        raw = str(text or "")
        email_match = re.search(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+[.][A-Za-z]{2,}", raw)
        company_match = re.search(
            r"(?:company|company name|الشركة|اسم الشركة)\s*[:=：-]\s*(.*?)(?=\s+(?:email|البريد الإلكتروني)\s*[:=：-]|$)",
            raw,
            re.IGNORECASE,
        )
        company_name = company_match.group(1).strip() if company_match else ""
        if not company_name and email_match:
            prefix = raw[:email_match.start()].strip()
            parts = [part.strip() for part in prefix.split("+") if part.strip()]
            if len(parts) >= 1 and "+" in prefix:
                company_name = parts[0]
        return {
            "email": email_match.group(0).strip().lower() if email_match else "",
            "company_name": company_name,
        }

    @staticmethod
    def extract_telegram_commercial_identity(text: str) -> dict[str, str]:
        return ChannelWebhookService.extract_commercial_identity(text)

    @staticmethod
    def extract_meta(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                metadata = value.get("metadata") or {}
                for message in value.get("messages") or []:
                    sender = str(message.get("from") or "")
                    items.append({
                        "kind": "message",
                        "external_message_id": str(message.get("id") or ""),
                        "external_user_id": sender,
                        "conversation_id": sender,
                        "text": str((message.get("text") or {}).get("body") or "").strip(),
                        "metadata": {"phone_number_id": metadata.get("phone_number_id"), "message_type": message.get("type")},
                    })
                for status in value.get("statuses") or []:
                    message_id = str(status.get("id") or "")
                    status_name = str(status.get("status") or "").strip().lower()
                    items.append({
                        "kind": "delivery",
                        "external_message_id": message_id,
                        "external_user_id": str(status.get("recipient_id") or ""),
                        "conversation_id": str(status.get("recipient_id") or ""),
                        "status": status_name,
                        "metadata": {
                            "phone_number_id": metadata.get("phone_number_id"),
                            "recipient_id": status.get("recipient_id"),
                            "timestamp": status.get("timestamp"),
                            "errors": status.get("errors") or [],
                        },
                    })
        return items


channel_webhook_service = ChannelWebhookService()
