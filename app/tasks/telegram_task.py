from __future__ import annotations

from app.services.telegram_menu_service import telegram_menu_service


def build_main_menu() -> dict:
    return telegram_menu_service.main_menu()


def build_service_menu(service: str) -> dict:
    return telegram_menu_service.submenu(service)


def route_callback(callback_data: str) -> dict:
    return telegram_menu_service.route_callback(callback_data)


def build_document_intake_request(*, telegram_user_id: int, chat_id: int, service: str) -> dict:
    if int(telegram_user_id or 0) <= 0 or int(chat_id or 0) <= 0:
        raise ValueError("telegram_identity_required")
    if service not in {"document_upload", "invoice_upload"}:
        raise ValueError("unsupported_intake_service")
    return {
        "schema": "kemet.telegram_intake.v1",
        "telegram_user_id": int(telegram_user_id),
        "chat_id": int(chat_id),
        "service": service,
        "status": "AWAITING_FILE",
        "execution_authority": False,
        "approval_required": True,
        "canonical_runtime": "kemet_canonical_runtime",
    }
