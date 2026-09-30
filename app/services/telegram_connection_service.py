"""Read-only Telegram connection and publishing-authority preflight."""
from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class TelegramConnectionService:
    VERSION = "1.0"
    SCHEMA = "kemet.telegram_connection.v1"

    def preflight(self, *, channel_ref: str | None = None) -> dict[str, Any]:
        token = os.getenv("TELEGRAM_TOKEN", "").strip()
        result: dict[str, Any] = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "configured": bool(token),
            "token_exposed": False,
            "connection": "NOT_CONFIGURED" if not token else "UNVERIFIED",
            "publishing_authority": "UNVERIFIED",
            "channel_ref": str(channel_ref or "").strip()[:200] or None,
            "side_effect": False,
            "execution_authority": False,
            "approval_required": True,
            "mcp": False,
        }
        if not token:
            return result
        try:
            bot = self._get(token, "getMe")
            result["bot"] = {"id": bot.get("id"), "username": bot.get("username"), "is_bot": bot.get("is_bot")}
            if not channel_ref:
                result["connection"] = "VERIFIED_BOT"
                return result
            chat = self._get(token, "getChat", {"chat_id": channel_ref})
            admins = self._get(token, "getChatAdministrators", {"chat_id": channel_ref})
            bot_id = bot.get("id")
            bot_admin = next((a for a in admins if a.get("user", {}).get("id") == bot_id), None)
            can_post = bool((bot_admin or {}).get("can_post_messages"))
            result["chat"] = {"id": chat.get("id"), "type": chat.get("type"), "title": chat.get("title"), "username": chat.get("username")}
            result["bot_admin"] = {"status": (bot_admin or {}).get("status"), "can_post_messages": can_post}
            result["connection"] = "VERIFIED"
            result["publishing_authority"] = "VERIFIED" if can_post else "INSUFFICIENT"
            return result
        except Exception as exc:
            result["connection"] = "FAILED_CLOSED"
            result["error"] = type(exc).__name__
            return result

    def send_message(self, *, chat_id: str, text: str, reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        token = os.getenv("TELEGRAM_TOKEN", "").strip()
        chat_id = str(chat_id or "").strip()
        text = str(text or "").strip()
        if not token or not chat_id or not text:
            raise ValueError("telegram_send_message_requirements_missing")
        params: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            import json
            params["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=query.encode("utf-8"), method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            import json
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok") is not True:
            raise RuntimeError("telegram_send_message_rejected")
        result = payload.get("result") or {}
        return {"ok": True, "message_id": result.get("message_id"), "chat_id": str((result.get("chat") or {}).get("id") or chat_id)}

    def edit_message(self, *, chat_id: str, message_id: int | str, text: str, reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        token = os.getenv("TELEGRAM_TOKEN", "").strip()
        chat_id = str(chat_id or "").strip()
        if not token or not chat_id or not str(text or "").strip():
            raise ValueError("telegram_edit_message_requirements_missing")
        params: dict[str, Any] = {"chat_id": chat_id, "message_id": str(message_id), "text": str(text).strip()}
        if reply_markup:
            import json
            params["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/editMessageText",
            data=query.encode("utf-8"), method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            import json
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok") is not True:
            raise RuntimeError("telegram_edit_message_rejected")
        result = payload.get("result") or {}
        return {"ok": True, "message_id": result.get("message_id", message_id), "chat_id": chat_id}

    def send_document(self, *, chat_id: str, document_path: str, caption: str | None = None) -> dict[str, Any]:
        token = os.getenv("TELEGRAM_TOKEN", "").strip()
        chat_id = str(chat_id or "").strip()
        from pathlib import Path
        target = Path(document_path)
        if not token or not chat_id or not target.is_file() or target.is_symlink():
            raise ValueError("telegram_send_document_requirements_missing")
        if target.stat().st_size > 25 * 1024 * 1024:
            raise ValueError("telegram_send_document_too_large")
        import mimetypes
        import uuid
        boundary = "----KemetBoundary" + uuid.uuid4().hex
        parts: list[bytes] = []
        def field(name: str, value: str) -> None:
            parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode("utf-8"))
        field("chat_id", chat_id)
        if caption:
            field("caption", str(caption)[:1024])
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        header = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"document\"; filename=\"{target.name}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
        body = b"".join(parts) + header + target.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            import json
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok") is not True:
            raise RuntimeError("telegram_send_document_rejected")
        result = payload.get("result") or {}
        return {"ok": True, "message_id": result.get("message_id"), "chat_id": str((result.get("chat") or {}).get("id") or chat_id), "filename": target.name}

    def answer_callback_query(self, *, callback_query_id: str) -> dict[str, Any]:
        token = os.getenv("TELEGRAM_TOKEN", "").strip()
        callback_query_id = str(callback_query_id or "").strip()
        if not token or not callback_query_id:
            raise ValueError("telegram_callback_query_requirements_missing")
        query = urllib.parse.urlencode({"callback_query_id": callback_query_id})
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            data=query.encode("utf-8"), method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            import json
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok") is not True:
            raise RuntimeError("telegram_answer_callback_rejected")
        return {"ok": True, "callback_query_id": callback_query_id}

    def download_file(self, *, file_id: str, destination: str) -> dict[str, Any]:
        token = os.getenv("TELEGRAM_TOKEN", "").strip()
        file_id = str(file_id or "").strip()
        if not token or not file_id:
            raise ValueError("telegram_download_requirements_missing")
        import json
        from pathlib import Path
        file_info = self._get(token, "getFile", {"file_id": file_id})
        file_path = str(file_info.get("file_path") or "").strip()
        if not file_path:
            raise RuntimeError("telegram_file_path_missing")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            f"https://api.telegram.org/file/bot{token}/{file_path}",
            method="GET", headers={"Accept": "*/*"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            target.write_bytes(response.read())
        return {"ok": True, "path": str(target), "file_path": file_path}

    @staticmethod
    def _get(token: str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = urllib.parse.urlencode(params or {})
        url = f"https://api.telegram.org/bot{token}/{method}"
        if query:
            url += "?" + query
        request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=15) as response:
            import json
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok") is not True:
            raise RuntimeError("telegram_api_rejected")
        return payload.get("result") or []


telegram_connection_service = TelegramConnectionService()
