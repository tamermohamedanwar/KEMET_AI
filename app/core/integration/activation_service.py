from typing import Any, Dict, Optional

from app.core.intelligence.intelligence_service import IntelligenceService, IntelligenceSignal
from app.core.revenue.revenue_engine import RevenueEngine
from app.core.sales.sales_engine import SalesEngine
from app.core.customer.customer_engine import CustomerEngine
from app.core.analytics.roi_engine import ROIEngine
from app.core.marketplace.marketplace_engine import MarketplaceEngine
from app.core.globalization.globalization_engine import GlobalizationEngine


class KemetActivationService:
    """
    Activation layer connecting Kemet foundation engines.

    The layer is intentionally governed:
    - advisory by default
    - no uncontrolled external execution
    - no direct database mutation
    - plans require approval
    """

    VERSION = "1.0"

    def __init__(self):
        self.intelligence = IntelligenceService()
        self.revenue = RevenueEngine()
        self.sales = SalesEngine()
        self.customer = CustomerEngine()
        self.analytics = ROIEngine()
        self.marketplace = MarketplaceEngine()
        self.globalization = GlobalizationEngine()

    def status(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "engine": "kemet_activation",
            "version": self.VERSION,
            "mode": "advisory",
            "connected_engines": [
                "intelligence",
                "revenue",
                "sales",
                "customer",
                "analytics",
                "marketplace",
                "globalization",
            ],
            "external_execution": False,
            "database_mutation": False,
            "approval_required": True,
        }

    def analyze(
        self,
        revenue_data: Optional[Dict[str, Any]] = None,
        sales_data: Optional[Dict[str, Any]] = None,
        customer_data: Optional[Dict[str, Any]] = None,
        analytics_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        revenue_data = revenue_data or {}
        sales_data = sales_data or {}
        customer_data = customer_data or {}
        analytics_data = analytics_data or {}

        revenue_result = self.revenue.analyze(
            leads=revenue_data.get("leads", 0),
            opportunities=revenue_data.get("opportunities", 0),
            customers=revenue_data.get("customers", 0),
            revenue=revenue_data.get("revenue", 0.0),
            pipeline_value=revenue_data.get("pipeline_value", 0.0),
        )

        sales_result = self.sales.analyze(
            leads=sales_data.get("leads", 0),
            qualified_leads=sales_data.get("qualified_leads", 0),
            opportunities=sales_data.get("opportunities", 0),
            customers=sales_data.get("customers", 0),
            pipeline_value=sales_data.get("pipeline_value", 0.0),
        )

        customer_result = self.customer.build_customer_context(
            customer_id=str(customer_data.get("customer_id", "anonymous")),
            channel=str(customer_data.get("channel", "web")),
            message=str(customer_data.get("message", "")),
        )

        roi_result = self.analytics.calculate(
            revenue=analytics_data.get("revenue", 0.0),
            cost=analytics_data.get("cost", 0.0),
            customers=analytics_data.get("customers", 0),
            leads=analytics_data.get("leads", 0),
            automated_tasks=analytics_data.get("automated_tasks", 0),
            manual_hours_saved=analytics_data.get("manual_hours_saved", 0.0),
        )

        signals = [
            IntelligenceSignal(
                key="revenue",
                title="Revenue Signal",
                priority=str(revenue_result.get("priority", "medium")),
                category="revenue",
                message=revenue_result.get("focus", "Review revenue"),
                action="review_revenue",
                confidence=0.90,
                source="revenue_engine",
            ),
            IntelligenceSignal(
                key="sales",
                title="Sales Signal",
                priority=str(sales_result.get("priority", "medium")),
                category="sales",
                message=sales_result.get("focus", "Review sales"),
                action="review_sales",
                confidence=0.90,
                source="sales_engine",
            ),
        ]

        intelligence_payload = [
            {
                "key": signal.key,
                "title": signal.title,
                "priority": signal.priority,
                "category": signal.category,
                "message": signal.message,
                "action": signal.action,
                "confidence": signal.confidence,
                "source": signal.source,
            }
            for signal in signals
        ]

        intelligence_result = self.intelligence.rank_signals(
            intelligence_payload
        )

        return {
            "ok": True,
            "mode": "advisory",
            "intelligence": intelligence_result,
            "revenue": revenue_result,
            "sales": sales_result,
            "customer": customer_result,
            "analytics": roi_result,
            "external_execution": False,
            "database_mutation": False,
        }

    def build_activation_plan(
        self,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:

        intelligence = analysis.get("intelligence", {})
        top_signal = None

        if isinstance(intelligence, dict):
            ranked = intelligence.get("signals", [])
            if ranked:
                top_signal = ranked[0]

        focus = (
            top_signal.get("message")
            if isinstance(top_signal, dict)
            else "Review business performance"
        )

        return {
            "ok": True,
            "engine": "kemet_activation",
            "version": self.VERSION,
            "status": "waiting_approval",
            "focus": focus,
            "requires_approval": True,
            "external_execution": False,
            "database_mutation": False,
        }

    def run(
        self,
        revenue_data: Optional[Dict[str, Any]] = None,
        sales_data: Optional[Dict[str, Any]] = None,
        customer_data: Optional[Dict[str, Any]] = None,
        analytics_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        analysis = self.analyze(
            revenue_data=revenue_data,
            sales_data=sales_data,
            customer_data=customer_data,
            analytics_data=analytics_data,
        )

        plan = self.build_activation_plan(analysis)

        return {
            "ok": True,
            "status": plan["status"],
            "analysis": analysis,
            "plan": plan,
            "approval_required": True,
            "external_execution": False,
            "database_mutation": False,
        }
