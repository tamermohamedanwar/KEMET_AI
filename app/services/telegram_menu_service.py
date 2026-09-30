from __future__ import annotations

from typing import Any

from app.services.channel_catalog_service import channel_catalog_service


class TelegramMenuService:
    """Canonical button-first Telegram navigation; no business execution authority."""

    VERSION = "2.2"
    SCHEMA = "kemet.telegram_menu.v2"

    LANGUAGE_BUTTONS = (
        ("🇪🇬 العربية | Arabic", "lang:ar"),
        ("🇬🇧 English | الإنجليزية", "lang:en"),
    )

    # Customer-facing catalog is canonical and channel-neutral.
    MAIN = channel_catalog_service.MAIN
    BUSINESS_TOOLS = channel_catalog_service.items("business_tools")
    MORE = channel_catalog_service.items("more")
    SUBMENUS = channel_catalog_service.SUBMENUS

    def language_menu(self) -> dict[str, Any]:
        return self._keyboard(
            "اختر اللغة / Choose your language",
            self.LANGUAGE_BUTTONS,
            home=True,
        )

    def main_menu(self, *, language: str | None = None) -> dict[str, Any]:
        lang = self._normalize_language(language)
        title = (
            "مرحبًا بك في Kemet 👋\nاختر ما تريد:"
            if lang == "ar"
            else "Welcome to Kemet 👋\nChoose what you need:"
            if lang == "en"
            else "مرحبًا بك في Kemet 👋 / Welcome to Kemet 👋\n\nاختر ما تريد / Choose what you need:"
        )
        return self._keyboard(title, self.MAIN, language=lang, language_switch=True)

    def submenu(self, service: str, *, language: str | None = None) -> dict[str, Any]:
        key = str(service or "").strip().lower()
        if key == "more":
            items = self.MORE
        elif key in self.SUBMENUS:
            items = self.SUBMENUS[key]
        else:
            raise ValueError("unknown_service")
        return self._keyboard(
            self._section_title(key, language),
            items,
            back=True,
            home=True,
            language=self._normalize_language(language),
        )

    def route_callback(self, callback: str) -> dict[str, Any]:
        value = str(callback or "").strip().lower()
        if value in {"home", "main"}:
            return {"action": "main_menu", "execution": False, "approval_required": True}
        if value in {"language", "languages"}:
            return {"action": "language_menu", "execution": False, "approval_required": True}
        if value.startswith("lang:"):
            lang = value.split(":", 1)[1]
            if lang not in {"ar", "en"}:
                raise ValueError("unsupported_language")
            return {"action": "main_menu", "language": lang, "execution": False, "approval_required": True}
        if value in self.SUBMENUS or value == "more":
            return {"action": "submenu", "service": value, "execution": False, "approval_required": True}
        actions = {item[1] for items in self.SUBMENUS.values() for item in items}
        if value in actions:
            return {
                "action": value,
                "execution": False,
                "approval_required": True,
                "canonical_runtime": "kemet_canonical_runtime",
            }
        raise ValueError("unknown_callback")

    @staticmethod
    def _normalize_language(language: str | None) -> str:
        value = str(language or "").strip().lower()
        return value if value in {"ar", "en"} else "bilingual"

    @staticmethod
    def _section_title(service: str, language: str | None) -> str:
        titles = {
            "jobs": ("💼 الوظائف | Jobs", "اختر ما تريد / Choose an option:"),
            "services": ("🛠️ الخدمات | Services", "اختر الخدمة / Choose a service:"),
            "financing": ("💰 التمويل | Financing", "اختر ما تريد / Choose an option:"),
            "more": ("⋯ المزيد | More", "المزيد من خدمات Kemet / More Kemet features:"),
            "business_tools": ("📦 أدوات الأعمال | Business Tools", "اختر أداة الأعمال / Choose a business tool:"),
            "products": ("🛍️ المنتجات | Products", "اختر المنتج / Choose a product:"),
            "document": ("📄 المستندات | Documents", "اختر الإجراء / Choose an action:"),
            "invoice": ("🧾 الفواتير | Invoices", "اختر الإجراء / Choose an action:"),
            "data": ("📊 البيانات | Data Tools", "اختر الأداة / Choose a tool:"),
            "orders": ("📋 طلباتي | My Requests", "اختر ما تريد / Choose an option:"),
            "support": ("📞 الدعم | Support", "كيف يمكننا مساعدتك؟ / How can we help?"),
            "automation": ("⚙️ الأتمتة | Automation", "اختر ما تريد / Choose an option:"),
        }
        heading, subtitle = titles.get(service, ("Kemet", "Choose an option:"))
        return f"{heading}\n\n{subtitle}"

    @staticmethod
    def _keyboard(
        title: str,
        items: tuple[tuple[str, str], ...],
        *,
        back: bool = False,
        home: bool = False,
        language: str = "bilingual",
        language_switch: bool = False,
    ) -> dict[str, Any]:
        rows = [[{"text": label, "callback_data": callback}] for label, callback in items]
        if language_switch:
            rows.append([{"text": "🌐 اللغة | Language", "callback_data": "language"}])
        if back:
            rows.append([{"text": "↩️ رجوع | Back", "callback_data": "home"}])
        if home and not back:
            rows.append([{"text": "🏠 الرئيسية | Home", "callback_data": "home"}])
        return {
            "schema": TelegramMenuService.SCHEMA,
            "version": TelegramMenuService.VERSION,
            "text": title,
            "language": language,
            "reply_markup": {"inline_keyboard": rows},
            "execution_authority": False,
            "approval_required": True,
        }


telegram_menu_service = TelegramMenuService()
