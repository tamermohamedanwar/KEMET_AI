from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.automation.action_registry import registry
from app.automation.engine import engine
from app.automation.workflow_planner import build_steps, summarize_steps


@dataclass
class OrchestratorPlan:
    intent: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    requires_approval: bool = False
    reason: str | None = None


class AIOrchestrator:
    """
    KEMET AI BOS orchestration layer.

    Responsibilities:
    - Understand business commands.
    - Build a safe execution plan.
    - Validate actions and parameters.
    - Route execution through the existing Automation Engine.
    - Never execute arbitrary AI-proposed actions directly.
    """

    ALLOWED_ACTIONS = {
        "sales_follow_up",
        "order_tracking",
        "refund_request",
        "payment_issue",
        "account_help",
        "lead_scoring",
        "customer_retention",
        "churn_detection",
        "revenue_opportunity",
        "ai_sales_qualification",
        "send_notification",
        "create_ticket",
        "smart_ticket_ai",
        "business_insights",
    }

    APPROVAL_ACTIONS = {
        "refund_request",
        "sales_follow_up",
    }

    HIGH_RISK_ACTIONS = {
        "refund_request",
        "send_notification",
        "sales_follow_up",
    }

    LOW_CONFIDENCE_THRESHOLD = 0.80

    def __init__(self):
        self.registry = registry
        self.engine = engine

    def _normalize(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _extract_order_id(self, text: str) -> str | None:
        match = re.search(r"\b([A-Za-z]{2,10}[-_]\d{2,20})\b", text or "")
        return match.group(1) if match else None

    def _extract_numeric_id(self, text: str) -> int | None:
        match = re.search(
            r"(?:customer|client|lead|عميل|العميل|عميله)"
            r"\s*(?:number|no|id|رقم|رقم العميل)?"
            r"\s*[:#-]?\s*(\d+)",
            text or "",
            flags=re.IGNORECASE,
        )
        if match:
            return int(match.group(1))

        match = re.search(r"#\s*(\d+)", text or "")
        if match:
            return int(match.group(1))

        return None

    def understand(self, command: str) -> OrchestratorPlan:
        text = self._normalize(command)

        if not text:
            raise ValueError("Command is empty.")

        order_id = self._extract_order_id(text)
        numeric_id = self._extract_numeric_id(text)

        if (
            "refund" in text
            or "refund_request" in text
            or "استرجاع" in text
            or "استرداد" in text
            or "رجع المبلغ" in text
        ):
            return OrchestratorPlan(
                intent="refund_request",
                action="refund_request",
                parameters={},
                confidence=0.98,
                requires_approval=True,
                reason="Financial action requires human approval.",
            )

        if (
            order_id
            and (
                "track" in text
                or "order" in text
                or "tracking" in text
                or "تابع الطلب" in text
                or "الطلب" in text
            )
        ):
            return OrchestratorPlan(
                intent="order_tracking",
                action="order_tracking",
                parameters={"order_id": order_id},
                confidence=0.99,
            )

        if (
            "follow up" in text
            or "followup" in text
            or "follow-up" in text
            or "تابع العميل" in text
            or "تابع العملاء" in text
            or "متابعة العميل" in text
            or "متابعة العملاء" in text
        ):
            params = {}
            if numeric_id is not None:
                params["customer_id"] = numeric_id
                params["lead_id"] = numeric_id

            return OrchestratorPlan(
                intent="customer_follow_up",
                action="sales_follow_up",
                parameters=params,
                confidence=0.95,
            )

        if (
            "hot leads" in text
            or "hottest leads" in text
            or "lead scoring" in text
            or "score leads" in text
            or "العملاء المحتملين" in text
            or "العملاء الساخنين" in text
            or "تقييم العملاء" in text
        ):
            return OrchestratorPlan(
                intent="lead_scoring",
                action="lead_scoring",
                parameters={},
                confidence=0.94,
            )

        if (
            "churn" in text
            or "at risk" in text
            or "risk of churn" in text
            or "مهددين" in text
            or "خطر فقد" in text
            or "خطر ترك" in text
        ):
            return OrchestratorPlan(
                intent="churn_detection",
                action="churn_detection",
                parameters={},
                confidence=0.94,
            )

        if (
            "qualify" in text
            or "qualification" in text
            or "تأهيل العملاء" in text
            or "تأهيل العملاء المحتملين" in text
        ):
            return OrchestratorPlan(
                intent="sales_qualification",
                action="ai_sales_qualification",
                parameters={},
                confidence=0.93,
            )

        if (
            "revenue" in text
            or "opportunity" in text
            or "فرصة بيع" in text
            or "فرص الإيرادات" in text
        ):
            return OrchestratorPlan(
                intent="revenue_opportunity",
                action="revenue_opportunity",
                parameters={},
                confidence=0.92,
            )

        if (
            "retain" in text
            or "retention" in text
            or "احتفظ بالعملاء" in text
            or "الاحتفاظ بالعملاء" in text
        ):
            return OrchestratorPlan(
                intent="customer_retention",
                action="customer_retention",
                parameters={},
                confidence=0.92,
            )

        if (
            "payment" in text
            or "payment issue" in text
            or "مشكلة دفع" in text
            or "مشكلة الدفع" in text
        ):
            return OrchestratorPlan(
                intent="payment_issue",
                action="payment_issue",
                parameters={},
                confidence=0.92,
            )

        if any(x in text for x in (
            "marketing", "marketing analysis", "marketing performance", "تسويق", "التسويق",
            "finance analysis", "financial analysis", "financial performance", "finance performance", "مالية", "المالية",
            "operations analysis", "operations performance", "تشغيل", "العمليات",
            "contract analysis", "contracts", "contracting", "عقود", "التعاقدات",
            "real estate analysis", "real estate", "عقارات", "العقارات",
            "media analysis", "media performance", "sports business", "إعلام", "رياضة",
            "industry analysis", "industry performance", "صناعة", "الصناعة",
            "compare businesses", "business comparison", "مقارنة الأعمال", "مقارنة الشركات",
        )):
            domain = "general"
            if any(x in text for x in ("marketing", "تسويق", "التسويق")):
                domain = "marketing"
            elif any(x in text for x in ("finance", "financial", "مالية", "المالية")):
                domain = "finance"
            elif any(x in text for x in ("contract", "contracts", "عقود", "التعاقدات")):
                domain = "contracting"
            elif any(x in text for x in ("real estate", "عقارات", "العقارات")):
                domain = "real_estate"
            elif any(x in text for x in ("media", "sports", "إعلام", "رياضة")):
                domain = "media_sports"
            elif any(x in text for x in ("industry", "صناعة", "الصناعة")):
                domain = "industry"
            elif any(x in text for x in ("compare", "comparison", "مقارنة")):
                domain = "comparison"
            return OrchestratorPlan(
                intent="business_insights",
                action="business_insights",
                parameters={"domain": domain},
                confidence=0.91,
                reason="Read-only domain analysis request.",
            )

        if (
            "business performance" in text
            or "business performance analysis" in text
            or "analyze my business" in text
            or "analyze business" in text
            or "business analysis" in text
            or "show my kpis" in text
            or "show kpis" in text
            or "kpis" in text
            or "show my sales" in text
            or "show sales" in text
            or "sales performance" in text
            or "sales analysis" in text
            or "analyze sales" in text
            or "executive summary" in text
            or "executive snapshot" in text
            or "business insights" in text
            or "analyze revenue" in text
        ):
            return OrchestratorPlan(
                intent="business_insights",
                action="business_insights",
                parameters={},
                confidence=0.94,
                requires_approval=False,
                reason="Read-only business intelligence request.",
            )

        if (
            "support tickets" in text
            or "review support tickets" in text
            or "review tickets" in text
            or "support ticket" in text
            or "smart ticket" in text
            or "تذاكر الدعم" in text
            or "تذاكر الدعم الفني" in text
            or "التذاكر" in text
        ):
            return OrchestratorPlan(
                intent="smart_ticket_ai",
                action="smart_ticket_ai",
                parameters={},
                confidence=0.94,
            )

        if (
            "account" in text
            or "حساب" in text
        ):
            return OrchestratorPlan(
                intent="account_help",
                action="account_help",
                parameters={},
                confidence=0.88,
            )

        raise ValueError(
            "I could not safely map this command to a registered business action."
        )

    def validate(self, plan: OrchestratorPlan) -> OrchestratorPlan:
        if not self.registry.exists(plan.action):
            raise ValueError(
                f"Action is not registered: {plan.action}"
            )

        if plan.action not in self.ALLOWED_ACTIONS:
            raise ValueError(
                f"Action is not allowed by the Orchestrator: {plan.action}"
            )

        if plan.action in self.APPROVAL_ACTIONS:
            plan.requires_approval = True

        if plan.confidence < self.LOW_CONFIDENCE_THRESHOLD:
            raise ValueError("Command confidence is below the safe execution threshold.")

        if plan.action == "order_tracking":
            order_id = plan.parameters.get("order_id")
            if not order_id:
                raise ValueError("order_id is required.")

        if plan.action == "sales_follow_up":
            customer_id = plan.parameters.get("customer_id")
            if customer_id is not None and not isinstance(customer_id, int):
                raise ValueError("customer_id must be an integer.")

        return plan

    def plan(self, command: str) -> dict[str, Any]:
        plan = self.understand(command)
        plan = self.validate(plan)

        risk = "high" if (plan.requires_approval or plan.action in self.HIGH_RISK_ACTIONS) else "low"
        steps = build_steps(plan.action, plan.parameters)
        if plan.requires_approval:
            steps[0]["requires_approval"] = True
        expected_result = {
            "refund_request": "Prepare a refund workflow after human approval.",
            "order_tracking": "Return the current order tracking state.",
            "business_insights": "Return a read-only business intelligence summary.",
        }.get(plan.action, "Run the registered business action and return its result.")
        return {
            "success": True,
            "status": "planned",
            "intent": plan.intent,
            "action": plan.action,
            "parameters": plan.parameters,
            "confidence": plan.confidence,
            "requires_approval": plan.requires_approval,
            "risk": risk,
            "expected_result": expected_result,
            "approval_reason": plan.reason if plan.requires_approval else None,
            "reason": plan.reason,
            "steps": steps,
            "workflow": summarize_steps(steps),
        }

    def execute(
        self,
        command: str,
        organization_id: int | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        plan = self.understand(command)
        plan = self.validate(plan)

        if organization_id is None:
            return {
                "success": False,
                "status": "validation_error",
                "message": "organization_id is required for execution.",
                "plan": {
                    "intent": plan.intent,
                    "action": plan.action,
                    "parameters": plan.parameters,
                    "confidence": plan.confidence,
                    "requires_approval": plan.requires_approval,
                },
            }

        if plan.requires_approval:
            return {
                "success": False,
                "status": "waiting_approval",
                "intent": plan.intent,
                "action": plan.action,
                "parameters": plan.parameters,
                "confidence": plan.confidence,
                "requires_approval": True,
                "reason": plan.reason or "Human approval is required before execution.",
                "organization_id": organization_id,
                "user_id": user_id,
                "execution": {
                    "allowed": False,
                    "executed": False,
                    "external_execution": False,
                    "database_mutation": False,
                },
            }

        data = {
            "command": command,
            "organization_id": organization_id,
            "user_id": user_id,
            **plan.parameters,
        }

        from app.automation.dispatcher import dispatcher

        dispatch_result = dispatcher.dispatch(
            action=plan.action,
            organization_id=organization_id,
            data=data,
        )

        return {
            "success": bool(dispatch_result.get("success", False)),
            "status": dispatch_result.get("status", "blocked"),
            "intent": plan.intent,
            "action": plan.action,
            "parameters": plan.parameters,
            "confidence": plan.confidence,
            "requires_approval": plan.requires_approval,
            "workflow_id": dispatch_result.get("workflow_id"),
            "workflow_name": dispatch_result.get("workflow_name"),
            "result": dispatch_result.get("result"),
            "dispatch": dispatch_result,
        }


orchestrator = AIOrchestrator()
