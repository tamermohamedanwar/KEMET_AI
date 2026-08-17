import re


class AutomationRouter:
    """
    Routes ticket messages to exactly one automation workflow.
    """

    def route(self, message):
        text = (message or "").strip().lower()

        # Normalize Arabic punctuation and spacing.
        text = text.replace("؟", "?").replace("،", " ").replace("ـ", "")


        # Normalize Arabic punctuation and spacing.
        text = text.replace("؟", "?").replace("،", " ").replace("ـ", "")

        # ==================================================
        # HIGH-PRIORITY BUSINESS ROUTING
        # These checks must run before generic AI/support routing.
        # ==================================================

        # Revenue / sales opportunities
        revenue_patterns = [
            "enterprise",
            "business",
            "باقة للشركات",
            "باقة شركة",
            "باقات الشركات",
            "للشركات",
            "للشركة",
            "اشتراك للشركات",
            "اشتراك شركة",
            "شراء باقة",
            "عايز أشتري",
            "اريد شراء",
            "أريد شراء",
        ]

        if any(pattern in text for pattern in revenue_patterns):
            return "revenue_opportunity"

        # Explicit payment problems
        payment_priority_patterns = [
            "الدفع فشل",
            "فشل الدفع",
            "مشكلة في الدفع",
            "مشكله في الدفع",
            "تم خصم المبلغ",
            "خصم المبلغ",
            "لم يتم تأكيد الدفع",
            "لم يتم تأكيد الطلب",
            "payment failed",
            "payment issue",
            "charged but",
            "payment declined",
        ]

        if any(pattern in text for pattern in payment_priority_patterns):
            return "payment_issue"

        text = (message or "").strip().lower()

        # Normalize Arabic punctuation and spacing
        text = (
            text.replace("؟", "?")
                .replace("،", " ")
                .replace("ـ", "")
        )

        if not text:
            return "smart_ticket_ai"

        # --------------------------------------------------
        # Order tracking
        # --------------------------------------------------
        order_patterns = [
            r"\bord[-_ ]?\d+\b",
            r"\border\b",
            "طلب",
            "شحنة",
            "شحن",
            "توصيل",
            "التسليم",
            "موعد الوصول",
            "اين طلبي",
            "أين طلبي",
            "حالة الطلب",
            "حالة الشحنة",
            "الشحنة لم تصل",
            "لم يصل الطلب",
            "موقع الطلب",
            "تتبع الطلب",
            "تتبع الشحنة",
            "tracking",
            "track order",
            "order status",
            "shipment",
            "delivery",
        ]

        if any(
            re.search(pattern, text)
            for pattern in order_patterns
        ):
            return "order_tracking"

        # --------------------------------------------------
        # Payment issues
        # --------------------------------------------------
        payment_patterns = [
            "مشكلة في الدفع",
            "مشكله في الدفع",
            "الدفع فشل",
            "فشل الدفع",
            "تعذر الدفع",
            "تعذر اتمام الدفع",
            "لم يتم الدفع",
            "عملية الدفع",
            "مشكلة بالدفع",
            "تم خصم المبلغ",
            "خصم المبلغ",
            "المبلغ اتخصم",
            "المبلغ تم خصمه",
            "payment failed",
            "payment issue",
            "payment problem",
            "failed payment",
            "charged",
        ]

        if any(pattern in text for pattern in payment_patterns):
            return "payment_issue"

        # --------------------------------------------------
        # Refund / return requests
        # --------------------------------------------------
        refund_patterns = [
            "استرجاع المبلغ",
            "استرجاع المال",
            "اريد استرجاع",
            "أريد استرجاع",
            "طلب استرجاع",
            "استرداد المبلغ",
            "استرداد المال",
            "رد المبلغ",
            "ارجاع المبلغ",
            "إرجاع المبلغ",
            "refund",
            "refund request",
            "money back",
            "return payment",
        ]

        if any(pattern in text for pattern in refund_patterns):
            return "refund_request"

        # --------------------------------------------------
        # Account help
        # --------------------------------------------------
        account_patterns = [
            "الحساب",
            "حسابي",
            "تسجيل الدخول",
            "تسجيل دخول",
            "دخول الحساب",
            "لا استطيع تسجيل الدخول",
            "لا أستطيع تسجيل الدخول",
            "نسيت كلمة المرور",
            "كلمة المرور",
            "تغيير كلمة المرور",
            "بيانات الحساب",
            "account",
            "my account",
            "login",
            "log in",
            "password",
        ]

        if any(pattern in text for pattern in account_patterns):
            return "account_help"

        # --------------------------------------------------
        # Notification requests/events
        # --------------------------------------------------
        # Payment issues must take priority over order tracking.
        payment_priority_patterns = [
            "الدفع فشل",
            "فشل الدفع",
            "مشكلة في الدفع",
            "مشكله في الدفع",
            "تم خصم المبلغ",
            "خصم المبلغ",
            "لم يتم تأكيد الدفع",
            "لم يتم تأكيد الطلب",
            "payment failed",
            "payment issue",
            "charged but",
            "payment declined",
        ]

        if any(pattern in text for pattern in payment_priority_patterns):
            return "payment_issue"

        # Refund requests.
        refund_patterns = [
            "استرجاع",
            "استرداد",
            "رد المبلغ",
            "ارجاع المبلغ",
            "إرجاع المبلغ",
            "refund",
            "refund request",
        ]

        if any(pattern in text for pattern in refund_patterns):
            return "refund_request"

        notification_patterns = [
            "إشعار",
            "اشعار",
            "notification",
            "notify",
            "تنبيه",
            "alert",
            "أرسل إشعار",
            "ارسل إشعار",
            "إرسال إشعار",
            "ارسال إشعار",
        ]

        if any(pattern in text for pattern in notification_patterns):
            return "send_notification"

        # --------------------------------------------------
        # New customer message / ticket
        # --------------------------------------------------
        ticket_patterns = [
            "رسالة جديدة من العميل",
            "العميل أرسل رسالة",
            "العميل ارسل رسالة",
            "رسالة العميل",
            "customer message",
            "new customer message",
            "new ticket",
        ]

        if any(pattern in text for pattern in ticket_patterns):
            return "smart_ticket_ai"

        # --------------------------------------------------
        # General AI support
        # --------------------------------------------------
        support_patterns = [
            "مساعدة",
            "مشكلة",
            "استفسار",
            "دعم",
            "support",
            "help",
            "problem",
            "issue",
            "فاتورة",
            "invoice",
            "سؤال",
            "معلومات",
        ]

        if any(pattern in text for pattern in support_patterns):
            return "generate_ai_reply"

        # --------------------------------------------------
        # Default
        # --------------------------------------------------
        return "smart_ticket_ai"
