from datetime import datetime, timedelta

from sqlalchemy import func

from app import db
from app.models.automation import AutomationWorkflow, AutomationExecution
from app.models.ticket import Ticket
from app.models.ticket_reply import TicketReply
from app.models.demo_lead import DemoLead
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.ai_usage import AIUsage


class KPIService:
    PERIODS = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
    }

    @classmethod
    def _start_date(cls, period):
        days = cls.PERIODS.get(period, 30)
        return datetime.utcnow() - timedelta(days=days)

    @classmethod
    def _safe_rate(cls, numerator, denominator):
        if not denominator:
            return 0.0
        return round((numerator / denominator) * 100, 2)

    @classmethod
    def get_kpis(cls, organization_id=None, period="30d"):
        period = period if period in cls.PERIODS else "30d"
        start_date = cls._start_date(period)

        # ---------------------------------------------------------
        # AUTOMATION
        # ---------------------------------------------------------
        workflow_query = AutomationWorkflow.query

        execution_query = AutomationExecution.query.filter(
            AutomationExecution.created_at >= start_date
        )

        if organization_id is not None:
            workflow_query = workflow_query.filter(
                AutomationWorkflow.organization_id == organization_id
            )

            execution_query = execution_query.join(
                AutomationWorkflow,
                AutomationExecution.workflow_id == AutomationWorkflow.id,
            ).filter(
                AutomationWorkflow.organization_id == organization_id
            )

        total_workflows = workflow_query.count()
        active_workflows = workflow_query.filter(
            AutomationWorkflow.is_active.is_(True)
        ).count()

        total_executions = execution_query.count()
        successful_executions = execution_query.filter(
            AutomationExecution.status == "completed"
        ).count()
        failed_executions = execution_query.filter(
            AutomationExecution.status == "failed"
        ).count()

        # ---------------------------------------------------------
        # SUPPORT
        # ---------------------------------------------------------
        ticket_query = Ticket.query.filter(
            Ticket.created_at >= start_date
        )

        if organization_id is not None:
            ticket_query = ticket_query.filter(
                Ticket.organization_id == organization_id
            )

        tickets_total = ticket_query.count()
        tickets_open = ticket_query.filter(Ticket.status == "open").count()
        tickets_pending = ticket_query.filter(
            Ticket.status == "pending"
        ).count()
        tickets_closed = ticket_query.filter(
            Ticket.status == "closed"
        ).count()

        reply_query = TicketReply.query.filter(
            TicketReply.created_at >= start_date
        )

        if organization_id is not None:
            reply_query = reply_query.join(
                Ticket,
                TicketReply.ticket_id == Ticket.id,
            ).filter(
                Ticket.organization_id == organization_id
            )

        ai_replies = reply_query.filter(
            TicketReply.is_ai.is_(True)
        ).count()

        staff_replies = reply_query.filter(
            TicketReply.is_staff.is_(True)
        ).count()

        # ---------------------------------------------------------
        # SALES / LEADS
        # ---------------------------------------------------------
        lead_query = DemoLead.query.filter(
            DemoLead.created_at >= start_date
        )

        if organization_id is not None:
            lead_query = lead_query.filter(
                DemoLead.organization_id == organization_id
            )

        leads_total = lead_query.count()

        leads_by_status = {}
        for row in (
            lead_query.with_entities(
                DemoLead.status,
                func.count(DemoLead.id),
            )
            .group_by(DemoLead.status)
            .all()
        ):
            leads_by_status[row[0] or "unknown"] = row[1]

        # ---------------------------------------------------------
        # PAYMENTS
        # ---------------------------------------------------------
        payment_query = Payment.query.filter(
            Payment.created_at >= start_date
        )

        if organization_id is not None:
            payment_query = payment_query.filter(
                Payment.organization_id == organization_id
            )

        payments_total = payment_query.count()
        payments_paid = payment_query.filter(
            Payment.status == "paid"
        ).count()
        payments_pending = payment_query.filter(
            Payment.status == "pending"
        ).count()
        payments_failed = payment_query.filter(
            Payment.status == "failed"
        ).count()

        paid_amount = (
            payment_query
            .filter(Payment.status == "paid")
            .with_entities(func.coalesce(func.sum(Payment.amount), 0))
            .scalar()
            or 0
        )

        # ---------------------------------------------------------
        # SUBSCRIPTIONS
        # ---------------------------------------------------------
        subscription_query = Subscription.query

        if organization_id is not None:
            subscription_query = subscription_query.filter(
                Subscription.organization_id == organization_id
            )

        subscriptions_total = subscription_query.count()
        subscriptions_active = subscription_query.filter(
            Subscription.status == "active"
        ).count()

        # ---------------------------------------------------------
        # AI USAGE
        # ---------------------------------------------------------
        usage_query = AIUsage.query

        if organization_id is not None:
            usage_query = usage_query.filter(
                AIUsage.organization_id == organization_id
            )

        usage_rows = usage_query.all()

        ai_requests = sum(
            int(getattr(row, "requests", 0) or 0)
            for row in usage_rows
        )

        ai_tokens = sum(
            int(getattr(row, "tokens", 0) or 0)
            for row in usage_rows
        )

        return {
            "period": period,
            "start_date": start_date.isoformat(),

            "automation": {
                "total_workflows": total_workflows,
                "active_workflows": active_workflows,
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "failed_executions": failed_executions,
                "success_rate": cls._safe_rate(
                    successful_executions,
                    total_executions,
                ),
            },

            "support": {
                "tickets_total": tickets_total,
                "tickets_open": tickets_open,
                "tickets_pending": tickets_pending,
                "tickets_closed": tickets_closed,
                "ai_replies": ai_replies,
                "staff_replies": staff_replies,
            },

            "sales": {
                "leads_total": leads_total,
                "leads_by_status": leads_by_status,
            },

            "revenue": {
                "payments_total": payments_total,
                "payments_paid": payments_paid,
                "payments_pending": payments_pending,
                "payments_failed": payments_failed,
                "paid_amount": float(paid_amount),
                "subscriptions_total": subscriptions_total,
                "subscriptions_active": subscriptions_active,
            },

            "ai": {
                "requests": ai_requests,
                "tokens": ai_tokens,
            },
        }
