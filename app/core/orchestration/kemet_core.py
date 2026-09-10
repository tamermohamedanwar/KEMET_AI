from typing import Any, Dict, Optional


class KemetCore:
    """
    Central coordination layer for Kemet.

    This layer coordinates intelligence, revenue, customer,
    sales, analytics, marketplace and globalization engines.

    It is intentionally advisory-only at this stage.
    """

    VERSION = "1.0"

    LAYERS = (
        "foundation",
        "command_center",
        "intelligence",
        "execution",
        "revenue",
        "customer",
        "sales",
        "analytics",
        "marketplace",
        "globalization",
    )

    def __init__(self):
        self.mode = "advisory"

    def status(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "engine": "kemet_core",
            "version": self.VERSION,
            "mode": self.mode,
            "layers": list(self.LAYERS),
            "layer_count": len(self.LAYERS),
            "external_execution": False,
            "database_mutation": False,
        }

    def build_context(
        self,
        business: Optional[Dict[str, Any]] = None,
        customer: Optional[Dict[str, Any]] = None,
        revenue: Optional[Dict[str, Any]] = None,
        sales: Optional[Dict[str, Any]] = None,
        signals: Optional[list] = None,
    ) -> Dict[str, Any]:
        return {
            "business": business or {},
            "customer": customer or {},
            "revenue": revenue or {},
            "sales": sales or {},
            "signals": signals or [],
            "mode": self.mode,
            "external_execution": False,
            "database_mutation": False,
        }

    def decide(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        signals = context.get("signals") or []

        if signals:
            ordered = sorted(
                signals,
                key=lambda item: (
                    item.get("priority", 0),
                    item.get("confidence", 0),
                ),
                reverse=True,
            )
            top = ordered[0]
            focus = top.get("focus") or top.get("message") or "Review business signals"
            priority = top.get("priority", 0)
            confidence = top.get("confidence", 0)
        else:
            focus = "Review business performance"
            priority = 0
            confidence = 0

        return {
            "ok": True,
            "focus": focus,
            "priority": priority,
            "confidence": confidence,
            "decision": "advisory",
            "requires_approval": True,
            "external_execution": False,
            "database_mutation": False,
        }

    def plan(
        self,
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "ok": True,
            "engine": "kemet_core",
            "version": self.VERSION,
            "status": "waiting_approval",
            "decision": decision,
            "requires_approval": True,
            "external_execution": False,
            "database_mutation": False,
        }

    def run(
        self,
        business: Optional[Dict[str, Any]] = None,
        customer: Optional[Dict[str, Any]] = None,
        revenue: Optional[Dict[str, Any]] = None,
        sales: Optional[Dict[str, Any]] = None,
        signals: Optional[list] = None,
    ) -> Dict[str, Any]:
        context = self.build_context(
            business=business,
            customer=customer,
            revenue=revenue,
            sales=sales,
            signals=signals,
        )

        decision = self.decide(context)
        plan = self.plan(decision)

        return {
            "ok": True,
            "status": "waiting_approval",
            "context": context,
            "decision": decision,
            "plan": plan,
            "mode": self.mode,
            "external_execution": False,
            "database_mutation": False,
        }
