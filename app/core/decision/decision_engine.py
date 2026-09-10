from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class BusinessDecision:
    decision_id: str
    area: str
    priority: str
    title: str
    focus: str
    rationale: str
    recommended_action: str
    confidence: float
    impact_score: float
    urgency_score: float
    metrics: Dict[str, Any]
    requires_approval: bool = True
    external_execution: bool = False
    database_mutation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DecisionEngine:
    VERSION = "2.0"

    DOMAINS = (
        "revenue",
        "sales",
        "customer",
        "operations",
        "automation",
        "growth",
        "roi",
    )

    def _clamp(self, value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    def _intent_weights(self, text: str) -> Dict[str, float]:
        weights = {domain: 1.0 for domain in self.DOMAINS}

        if any(x in text for x in (
            "revenue", "money", "profit", "income",
            "ربح", "إيراد", "فلوس", "دخل",
        )):
            weights["revenue"] = 2.5

        if any(x in text for x in (
            "sales", "lead", "deal", "pipeline",
            "بيع", "مبيعات", "فرصة", "عملاء محتملين",
        )):
            weights["sales"] = 2.5

        if any(x in text for x in (
            "support", "ticket", "customer", "client",
            "دعم", "تذكرة", "عميل", "خدمة",
        )):
            weights["customer"] = 2.5

        if any(x in text for x in (
            "operation", "operations", "workflow", "task",
            "تشغيل", "عمليات", "مهمة",
        )):
            weights["operations"] = 2.5

        if any(x in text for x in (
            "automation", "automations", "execution",
            "أتمتة", "تنفيذ",
        )):
            weights["automation"] = 2.5

        if any(x in text for x in (
            "growth", "scale", "grow",
            "نمو", "توسع",
        )):
            weights["growth"] = 2.5

        if any(x in text for x in (
            "roi", "return", "efficiency",
            "عائد", "كفاءة",
        )):
            weights["roi"] = 2.5

        return weights

    def _score_domains(
        self,
        business: Dict[str, Any],
        command: str,
    ) -> Dict[str, Dict[str, float]]:
        revenue = float(business.get("revenue", 0) or 0)
        leads = int(business.get("leads", 0) or 0)
        qualified = int(business.get("qualified_leads", 0) or 0)
        converted = int(business.get("converted_leads", 0) or 0)
        customers = int(business.get("customers", 0) or 0)
        open_tickets = int(business.get("open_tickets", 0) or 0)
        executions = int(business.get("automation_executions", 0) or 0)
        successful = int(business.get("successful_executions", 0) or 0)
        hours_saved = float(business.get("manual_hours_saved", 0) or 0)
        lead_rate = float(business.get("lead_to_customer_rate", 0) or 0)

        success_rate = (
            successful / executions * 100
            if executions
            else 100.0
        )

        sales_gap = max(0, qualified - converted)

        scores = {
            "revenue": {
                "impact": self._clamp(
                    min(100, sales_gap * 15 + leads * 5 + (30 if revenue == 0 else 0))
                ),
                "urgency": self._clamp(
                    sales_gap * 12 + (25 if leads > 0 and customers == 0 else 0)
                ),
            },
            "sales": {
                "impact": self._clamp(
                    qualified * 25 + sales_gap * 20 + leads * 5
                ),
                "urgency": self._clamp(
                    qualified * 20 + sales_gap * 25
                ),
            },
            "customer": {
                "impact": self._clamp(
                    open_tickets * 3
                ),
                "urgency": self._clamp(
                    open_tickets * 3.5
                ),
            },
            "operations": {
                "impact": self._clamp(
                    open_tickets * 1.5 + executions * 0.2
                ),
                "urgency": self._clamp(
                    open_tickets * 2 + (20 if executions == 0 else 0)
                ),
            },
            "automation": {
                "impact": self._clamp(
                    max(0, 100 - success_rate) * 1.5
                    + min(executions, 100) * 0.2
                ),
                "urgency": self._clamp(
                    max(0, 80 - success_rate) * 2
                ),
            },
            "growth": {
                "impact": self._clamp(
                    leads * 7
                    + qualified * 15
                    + (20 if customers == 0 and leads > 0 else 0)
                ),
                "urgency": self._clamp(
                    qualified * 15
                    + (20 if leads > 0 and customers == 0 else 0)
                ),
            },
            "roi": {
                "impact": self._clamp(
                    hours_saved * 2
                    + (20 if revenue > 0 else 0)
                ),
                "urgency": self._clamp(
                    hours_saved * 1.5
                ),
            },
        }

        intent = self._intent_weights(str(command or "").lower())

        for domain in self.DOMAINS:
            scores[domain]["intent"] = intent[domain]
            scores[domain]["score"] = round(
                (
                    scores[domain]["impact"] * 0.45
                    + scores[domain]["urgency"] * 0.35
                    + min(intent[domain] * 10, 25) * 0.20
                ),
                2,
            )

        return scores

    def decide(
        self,
        command: str,
        live_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = live_context or {}
        business = context.get("business", context)

        scores = self._score_domains(
            business=business,
            command=command,
        )

        ranked = sorted(
            scores.items(),
            key=lambda item: item[1]["score"],
            reverse=True,
        )

        area, selected = ranked[0]

        score = selected["score"]
        impact = selected["impact"]
        urgency = selected["urgency"]

        if score >= 70:
            priority = "critical"
        elif score >= 45:
            priority = "high"
        elif score >= 25:
            priority = "medium"
        else:
            priority = "low"

        revenue = float(business.get("revenue", 0) or 0)
        leads = int(business.get("leads", 0) or 0)
        qualified = int(business.get("qualified_leads", 0) or 0)
        converted = int(business.get("converted_leads", 0) or 0)
        customers = int(business.get("customers", 0) or 0)
        open_tickets = int(business.get("open_tickets", 0) or 0)
        executions = int(business.get("automation_executions", 0) or 0)
        successful = int(business.get("successful_executions", 0) or 0)

        success_rate = (
            successful / executions * 100
            if executions
            else 100.0
        )

        titles = {
            "revenue": "Revenue opportunity requires attention",
            "sales": "Sales pipeline requires conversion",
            "customer": "Customer operations require attention",
            "operations": "Business operations require optimization",
            "automation": "Automation reliability requires attention",
            "growth": "Growth opportunity requires attention",
            "roi": "Operational ROI can be improved",
        }

        focuses = {
            "revenue": "Convert demand into measurable revenue",
            "sales": "Convert qualified opportunities into customers",
            "customer": "Reduce unresolved customer workload",
            "operations": "Improve operational throughput",
            "automation": "Improve automation reliability",
            "growth": "Accelerate customer and revenue growth",
            "roi": "Scale high-value efficient operations",
        }

        actions = {
            "revenue": "Review revenue opportunities and prepare the highest-impact governed action.",
            "sales": "Prioritize qualified opportunities and prepare follow-up actions for approval.",
            "customer": "Prioritize unresolved customer cases and prepare governed follow-up actions.",
            "operations": "Review operational bottlenecks and prepare an optimization workflow for approval.",
            "automation": "Review failed or weak automation executions and prepare recovery actions for approval.",
            "growth": "Identify the strongest growth opportunities and prepare a governed growth workflow.",
            "roi": "Identify high-efficiency operations and prepare a governed scaling action.",
        }

        rationale = (
            f"Kemet ranked {area} as the highest-impact business domain "
            f"with a weighted score of {score:.2f}. "
            f"Impact={impact:.1f}, urgency={urgency:.1f}. "
            f"Live context: revenue={revenue:.2f}, leads={leads}, "
            f"qualified={qualified}, converted={converted}, "
            f"customers={customers}, open_tickets={open_tickets}, "
            f"automation_success_rate={success_rate:.1f}%."
        )

        confidence = self._clamp(
            50
            + score * 0.35
            + (15 if selected["intent"] > 1 else 0)
        ) / 100

        metrics = {
            "revenue": revenue,
            "leads": leads,
            "qualified_leads": qualified,
            "converted_leads": converted,
            "customers": customers,
            "open_tickets": open_tickets,
            "automation_executions": executions,
            "successful_executions": successful,
            "automation_success_rate": round(success_rate, 2),
            "impact_score": round(impact, 2),
            "urgency_score": round(urgency, 2),
            "weighted_score": round(score, 2),
            "domain_scores": scores,
        }

        decision = BusinessDecision(
            decision_id=f"kemet-decision-{area}-{priority}",
            area=area,
            priority=priority,
            title=titles[area],
            focus=focuses[area],
            rationale=rationale,
            recommended_action=actions[area],
            confidence=round(confidence, 4),
            impact_score=round(impact, 2),
            urgency_score=round(urgency, 2),
            metrics=metrics,
        )

        return {
            "success": True,
            "engine": "kemet_decision_engine",
            "version": self.VERSION,
            "mode": "advisory",
            "decision": decision.to_dict(),
            "requires_approval": True,
            "external_execution": False,
            "database_mutation": False,
        }
