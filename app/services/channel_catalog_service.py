from __future__ import annotations

from typing import Any


class ChannelCatalogService:
    """Single customer-facing catalog shared by Telegram and WhatsApp."""

    VERSION = "1.0"
    MAIN = (
        ("💼 الوظائف | Jobs", "jobs"),
        ("🛠️ الخدمات | Services", "services"),
        ("💰 التمويل | Financing", "financing"),
        ("📦 أدوات الأعمال | Business Tools", "business_tools"),
        ("📋 طلباتي | My Requests", "orders"),
        ("⋯ المزيد | More", "more"),
    )
    SUBMENUS = {
        "jobs": (("🔎 البحث عن وظيفة | Find a Job", "jobs_browse"), ("📂 المجالات | Categories", "jobs_categories"), ("❓ اسأل عن وظيفة | Ask About a Job", "jobs_question")),
        "financing": (("🔎 أبحث عن تمويل | Find Financing", "financing_browse"), ("📝 أريد التقديم | Request Financing", "financing_request"), ("ℹ️ كيف يعمل؟ | How it works", "financing_info")),
        "services": (("📄 ذكاء المستندات | Document Intelligence", "service_document"), ("📊 تنظيف البيانات | Data Cleaning", "service_data"), ("⚙️ الأتمتة | Automation", "service_automation"), ("💰 الأسعار | Pricing", "pricing")),
        "products": (("📦 المنتجات الرقمية | Digital Products", "products_digital"), ("🔍 التفاصيل | Details", "products_details")),
        "business_tools": (("🛍️ المنتجات | Products", "products"), ("📄 المستندات | Documents", "document"), ("🧾 الفواتير | Invoices", "invoice"), ("📊 البيانات | Data Tools", "data")),
        "document": (("📤 رفع مستند | Upload Document", "document_upload"), ("ℹ️ التفاصيل | Details", "document_details")),
        "invoice": (("📤 رفع فاتورة | Upload Invoice", "invoice_upload"), ("ℹ️ التفاصيل | Details", "invoice_details")),
        "data": (("📁 CSV / Excel", "data_files"), ("🧹 تنظيف البيانات | Data Cleaning", "data_cleaning")),
        "orders": (("📋 حالة الطلب | Order Status", "orders_status"), ("📦 التسليمات | Deliveries", "orders_deliveries")),
        "more": (("📞 الدعم | Support", "support"), ("⚙️ الأتمتة | Automation", "automation")),
        "support": (("❓ المساعدة | Help", "help"), ("👤 تواصل مع شخص | Human Support", "human_support")),
        "automation": (("🤖 اطلب أتمتة | Request Automation", "automation_request"), ("💡 أمثلة | Examples", "automation_examples")),
    }

    def items(self, section: str) -> tuple[tuple[str, str], ...]:
        key = str(section or "").strip().lower()
        if key in {"main", "home"}:
            return self.MAIN
        if key not in self.SUBMENUS:
            raise ValueError("unknown_catalog_section")
        return self.SUBMENUS[key]

    def whatsapp_home_text(self) -> str:
        lines = ["مرحبًا بك في Kemet 👋 / Welcome to Kemet 👋", "", "اختر ما تريد / Choose what you need:"]
        lines.extend(f"{i}. {label}" for i, (label, _) in enumerate(self.MAIN, 1))
        return "\n".join(lines)


channel_catalog_service = ChannelCatalogService()
