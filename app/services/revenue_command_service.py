from datetime import datetime, timedelta

from sqlalchemy import func

from app.models.demo_lead import DemoLead
from app.models.lead_activity import LeadActivity
from app.models.payment import Payment
from app.models.subscription import Subscription

from app.services.recurring_revenue_context_service import RecurringRevenueContextService

from app.services.recurring_revenue_service import RecurringRevenueService
from app.services.revenue_health_service import RevenueHealthService
from app.services.revenue_pipeline_service import revenue_pipeline_service

from app.services.revenue_decision_service import RevenueDecisionService, RevenueGrowthLoopService
from app.services.revenue_command_lead_service import RevenueCommandLeadService

from app.services.ai_sales_intelligence_service import AISalesIntelligenceService


class RevenueCommandService:

    @classmethod
    def get_dashboard(
        cls,
        organization_id=None,
        period="30d",
    ):
        period = period if period in RevenueCommandLeadService.PERIODS else "30d"
        start_date = RevenueCommandLeadService.start_date(period)
        now = datetime.utcnow()

        # =====================================================
        # LEADS / SALES PIPELINE
        # =====================================================

        lead_query = DemoLead.query.filter(
            DemoLead.created_at >= start_date
        )

        if organization_id is not None:
            lead_query = lead_query.filter(
                DemoLead.organization_id == organization_id
            )

        leads = lead_query.all()

        total_leads = len(leads)
        won_leads = 0
        lost_leads = 0
        active_leads = 0

        pipeline_value = 0.0
        won_value = 0.0
        weighted_pipeline = 0.0

        hot_leads = 0
        warm_leads = 0
        cold_leads = 0

        active_values = []
        won_values = []

        priority_leads = []

        for lead in leads:
            status = RevenueCommandLeadService.status(lead)
            value = RevenueCommandLeadService.value(lead)
            score = RevenueCommandLeadService.score(lead)

            if status in {"won", "converted"}:
                won_leads += 1
                won_value += value
                won_values.append(value)

            elif status == "lost":
                lost_leads += 1

            else:
                active_leads += 1
                pipeline_value += value
                active_values.append(value)

                probability = score / 100.0
                weighted_pipeline += value * probability

                action = RevenueCommandLeadService.next_best_action(
                    lead,
                    now,
                )

                priority_leads.append(
                    {
                        "id": lead.id,
                        "company_name": (
                            lead.company_name
                            or "Unnamed company"
                        ),
                        "email": lead.email or "",
                        "status": lead.status or "new",
                        "score": score,
                        "estimated_value": value,
                        "weighted_value": round(
                            value * probability,
                            2,
                        ),
                        "next_follow_up_at": (
                            lead.next_follow_up_at.isoformat()
                            if lead.next_follow_up_at
                            else None
                        ),
                        "next_action": action["label"],
                        "action_type": action["type"],
                        "action_priority": action["priority"],
                    }
                )

            if score >= 75:
                hot_leads += 1
            elif score >= 45:
                warm_leads += 1
            else:
                cold_leads += 1

        conversion_rate = (
            round(
                (won_leads / total_leads) * 100,
                2,
            )
            if total_leads
            else 0.0
        )

        average_deal_value = (
            round(
                won_value / won_leads,
                2,
            )
            if won_leads
            else 0.0
        )

        active_average_value = (
            round(
                pipeline_value / active_leads,
                2,
            )
            if active_leads
            else 0.0
        )

        # Expected revenue from current open pipeline.
        revenue_forecast = round(
            won_value + weighted_pipeline,
            2,
        )

        # How much open pipeline exists relative to closed revenue.
        pipeline_coverage = (
            round(
                pipeline_value / won_value,
                2,
            )
            if won_value > 0
            else 0.0
        )

        # =====================================================
        # PRIORITY OPPORTUNITIES
        # =====================================================

        priority_leads.sort(
            key=lambda item: (
                item["action_priority"],
                item["score"],
                item["weighted_value"],
                item["estimated_value"],
            ),
            reverse=True,
        )

        priority_leads = priority_leads[:10]

        # =====================================================
        # FOLLOW-UPS
        # =====================================================

        followup_query = LeadActivity.query.filter(
            LeadActivity.activity_type == "follow_up",
            LeadActivity.completed_at.is_(None),
        )

        if organization_id is not None:
            followup_query = followup_query.filter(
                LeadActivity.organization_id == organization_id
            )

        followups = followup_query.all()

        overdue_followups = 0
        today_followups = 0
        upcoming_followups = 0

        for item in followups:
            due_at = item.due_at

            if not due_at:
                upcoming_followups += 1
                continue

            if due_at.date() < now.date():
                overdue_followups += 1
            elif due_at.date() == now.date():
                today_followups += 1
            else:
                upcoming_followups += 1

        # =====================================================
        # PAYMENTS
        # =====================================================

        payment_query = Payment.query.filter(
            Payment.created_at >= start_date
        )

        if organization_id is not None:
            payment_query = payment_query.filter(
                Payment.organization_id == organization_id
            )

        payments_total = payment_query.count()

        paid_query = payment_query.filter(
            Payment.status == "paid"
        )

        paid_payments = paid_query.count()

        paid_amount = (
            paid_query
            .with_entities(
                func.coalesce(
                    func.sum(Payment.amount),
                    0,
                )
            )
            .scalar()
            or 0
        )

        pending_payments = payment_query.filter(
            Payment.status == "pending"
        ).count()

        failed_payments = payment_query.filter(
            Payment.status == "failed"
        ).count()

        # =====================================================
        # SUBSCRIPTIONS
        # =====================================================

        subscription_query = Subscription.query

        if organization_id is not None:
            subscription_query = subscription_query.filter(
                Subscription.organization_id == organization_id
            )

        active_subscriptions = subscription_query.filter(
            Subscription.status == "active"
        ).count()

        # =====================================================
        # LEAD DISTRIBUTION
        # =====================================================

        lead_distribution = {
            "hot": hot_leads,
            "warm": warm_leads,
            "cold": cold_leads,
        }

        # =====================================================
        # AI SALES INTELLIGENCE
        # =====================================================

        active_lead_objects = [
            lead
            for lead in leads
            if RevenueCommandLeadService.status(lead)
            not in {"won", "converted", "lost"}
        ]

        ai_ranked_leads = (
            AISalesIntelligenceService.rank_leads(
                active_lead_objects,
                limit=10,
            )
        )

        ai_actions = {}

        for item in ai_ranked_leads:
            action = item["next_best_action"]["action"]
            ai_actions[action] = (
                ai_actions.get(action, 0) + 1
            )

        # =====================================================
        # RETURN REVENUE INTELLIGENCE
        # =====================================================

        ranked_decisions = RevenueDecisionService.rank(
            active_lead_objects
        )

        decision_distribution = {}
        for item in ranked_decisions:
            priority = item["decision"]["priority"]
            decision_distribution[priority] = (
                decision_distribution.get(priority, 0) + 1
            )

        growth_loop = RevenueGrowthLoopService.summarize(
            leads
        )

        recurring_context = (
            RecurringRevenueContextService.build(
                organization_id=organization_id,
            )
        )

        recurring_revenue = (
            RecurringRevenueService.calculate(
                active_subscriptions=(
                    recurring_context[
                        "active_subscriptions"
                    ]
                ),
                monthly_revenue=(
                    recurring_context.get(
                        "monthly_recurring_revenue",
                        0.0,
                    )
                ),
            )
        )

        commercial_financials = revenue_pipeline_service.dashboard(
            organization_id=int(organization_id)
        )["financials"] if organization_id is not None else {
            "paid_revenue": 0.0,
            "verified_profit": 0.0,
            "profit_status": "not_verified",
        }
        verified_commercial_revenue = float(
            commercial_financials.get("paid_revenue", 0.0) or 0.0
        )

        health = RevenueHealthService.calculate(
            sales={
                "total_leads": total_leads,
                "won_leads": won_leads,
                "pipeline_value": pipeline_value,
                "weighted_pipeline": weighted_pipeline,
            },
            payments={
                "paid_amount": verified_commercial_revenue,
            },
            followups={
                "overdue": overdue_followups,
            },
        )

        return {
            "period": period,
            "start_date": start_date.isoformat(),

            "health": health,

            "measurement": {
                "mode": "observed_and_forecast",
                "authoritative_sources": [
                    "demo_leads",
                    "lead_activities",
                    "payments",
                    "subscriptions",
                ],
                "recorded_revenue_is_payment_backed": True,
                "verified_commercial_revenue_is_pipeline_bound": True,
                "forecast_is_not_recorded_revenue": True,
                "causal_claim": False,
                "observed_only_for_realized_metrics": True,
                "advisory_only": True,
                "auto_execute": False,
                "external_execution": False,
                "database_mutation": False,
                "tenant_scoped": organization_id is not None,
            },

            "growth_loop": growth_loop,

            "recurring_revenue": recurring_revenue,

            "sales": {
                "total_leads": total_leads,
                "active_leads": active_leads,
                "won_leads": won_leads,
                "lost_leads": lost_leads,
                "conversion_rate": conversion_rate,

                "pipeline_value": round(
                    pipeline_value,
                    2,
                ),

                "won_value": round(
                    won_value,
                    2,
                ),

                "weighted_pipeline": round(
                    weighted_pipeline,
                    2,
                ),

                "revenue_forecast": revenue_forecast,

                "average_deal_value": (
                    average_deal_value
                ),

                "active_average_value": (
                    active_average_value
                ),

                "pipeline_coverage": (
                    pipeline_coverage
                ),

                "hot_leads": hot_leads,
                "warm_leads": warm_leads,
                "cold_leads": cold_leads,

                "lead_distribution": (
                    lead_distribution
                ),
            },

            "ai_sales": {
                "ranked_leads": ai_ranked_leads,
                "action_distribution": ai_actions,
                "total_actionable": len(
                    active_lead_objects
                ),
            },

            "followups": {
                "overdue": overdue_followups,
                "today": today_followups,
                "upcoming": upcoming_followups,
                "open_total": len(followups),
            },

            "payments": {
                "total": payments_total,
                "paid": paid_payments,
                "pending": pending_payments,
                "failed": failed_payments,
                "paid_amount": round(
                    float(paid_amount),
                    2,
                ),
                "verified_commercial_revenue": round(
                    verified_commercial_revenue,
                    2,
                ),
                "revenue_authority": "revenue_pipeline_verified_payment_binding",
            },

            "subscriptions": {
                "active": active_subscriptions,
            },

            "priority_leads": priority_leads,

            "revenue_intelligence": {
                "ranked_decisions": ranked_decisions[:20],
                "priority_distribution": decision_distribution,
                "total_actionable": len(
                    [
                        item
                        for item in ranked_decisions
                        if item["decision"]["priority"] != "none"
                    ]
                ),
                "decision_basis": "lead_score_estimated_value_followup_state",
                "advisory_only": True,
                "causal_claim": False,
                "auto_execute": False,
            },
        }
