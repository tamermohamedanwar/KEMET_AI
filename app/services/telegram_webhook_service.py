from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any


class TelegramWebhookService:
    VERSION = "1.0"

    @staticmethod
    def set_webhook(public_url: str) -> dict[str, Any]:
        public_url = str(public_url or "").strip().rstrip("/")
        if not public_url.startswith("https://"):
            raise ValueError("https_public_url_required")
        token = os.getenv("TELEGRAM_TOKEN", "").strip()
        secret = os.getenv("KEMET_TELEGRAM_WEBHOOK_SECRET", "").strip()
        if not token or not secret:
            raise ValueError("telegram_webhook_credentials_required")
        organization_id = os.getenv("KEMET_TELEGRAM_ORGANIZATION_ID", "").strip()
        if not organization_id.isdigit() or int(organization_id) <= 0:
            raise ValueError("telegram_organization_required")
        endpoint = public_url.rstrip("/") + f"/api/bos/channels/telegram/webhook/{int(organization_id)}"
        body = urllib.parse.urlencode({
            "url": endpoint,
            "secret_token": secret,
            "allowed_updates": json.dumps(["message", "edited_message", "callback_query"]),
        }).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/setWebhook",
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok") is not True:
            raise RuntimeError("telegram_webhook_rejected")
        return {"ok": True, "endpoint": endpoint, "result": payload.get("result")}

    @staticmethod
    def get_webhook_info() -> dict[str, Any]:
        token = os.getenv("TELEGRAM_TOKEN", "").strip()
        if not token:
            raise ValueError("telegram_token_required")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/getWebhookInfo",
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok") is not True:
            raise RuntimeError("telegram_webhook_info_failed")
        result = payload.get("result") or {}
        return {
            "ok": True,
            "url_configured": bool(result.get("url")),
            "pending_update_count": result.get("pending_update_count", 0),
            "last_error_date": result.get("last_error_date"),
            "last_error_message": result.get("last_error_message"),
        }


telegram_webhook_service = TelegramWebhookService()
