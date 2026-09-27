from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class BusinessSnapshot:
    organization_id: Optional[int]
    organization_name: Optional[str]

    leads: int
    qualified_leads: int
    converted_leads: int
    lost_leads: int

    pipeline_value: float
    revenue: float

    customers: int
    users: int

    open_tickets: int
    total_tickets: int
    ticket_replies: int

    conversations: int
    chat_messages: int

    active_workflows: int
    automation_executions: int
    successful_executions: int

    ai_requests: int
    ai_tokens: int

    active_subscriptions: int
    paid_payments: int
    pending_payments: int

    lead_activities: int

    @property
    def opportunity_count(self) -> int:
        return self.qualified_leads

    @property
    def average_deal_value(self) -> float:
        if self.converted_leads <= 0:
            return 0.0
        return round(self.revenue / self.converted_leads, 2)

    @property
    def lead_to_customer_rate(self) -> float:
        if self.leads <= 0:
            return 0.0
        return round((self.converted_leads / self.leads) * 100, 2)

    @property
    def qualification_rate(self) -> float:
        if self.leads <= 0:
            return 0.0
        return round((self.qualified_leads / self.leads) * 100, 2)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["opportunities"] = self.opportunity_count
        data["average_deal_value"] = self.average_deal_value
        data["lead_to_customer_rate"] = self.lead_to_customer_rate
        data["qualification_rate"] = self.qualification_rate
        return data


class LiveBusinessData:
    """
    Read-only adapter between Kemet business engines and the existing
    application database.

    This class never creates, updates, deletes, or commits database records.
    """

    def __init__(self, db=None):
        self.db = db

    def _database(self):
        if self.db is not None:
            return self.db

        from app import db
        return db

    @staticmethod
    def _money(value: Any) -> float:
        if value is None:
            return 0.0

        if isinstance(value, Decimal):
            return float(value)

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def snapshot(self, organization_id: Optional[int] = None) -> BusinessSnapshot:
        from sqlalchemy import func

        from app.models.organization import Organization
        from app.models.user import User
        from app.models.demo_lead import DemoLead
        from app.models.payment import Payment
        from app.models.subscription import Subscription
        from app.models.ticket import Ticket
        from app.models.ticket_reply import TicketReply
        from app.models.conversation import Conversation
        from app.models.chat import ChatMessage
        from app.models.automation import AutomationWorkflow, AutomationExecution
        from app.models.ai_usage import AIUsage
        from app.models.lead_activity import LeadActivity

        db = self._database()

        def query(model):
            q = model.query
            if organization_id is not None:
                if hasattr(model, "organization_id"):
                    q = q.filter(model.organization_id == organization_id)
            return q

        organization_name = None

        if organization_id is not None:
            organization = Organization.query.filter(
                Organization.id == organization_id
            ).first()

            if organization is not None:
                organization_name = organization.name

        leads_query = query(DemoLead)
        leads = leads_query.count()
        qualified_leads = leads_query.filter(
            func.lower(DemoLead.status) == "qualified"
        ).count()
        converted_leads = leads_query.filter(
            func.lower(DemoLead.status) == "converted"
        ).count()
        lost_leads = leads_query.filter(
            func.lower(DemoLead.status) == "lost"
        ).count()

        pipeline_value = leads_query.with_entities(
            func.coalesce(func.sum(DemoLead.estimated_value), 0)
        ).scalar()

        paid_payments_query = query(Payment).filter(
            func.lower(Payment.status) == "paid"
        )

        pending_payments_query = query(Payment).filter(
            func.lower(Payment.status) == "pending"
        )

        revenue = paid_payments_query.with_entities(
            func.coalesce(func.sum(Payment.amount), 0)
        ).scalar()

        paid_payments = paid_payments_query.count()
        pending_payments = pending_payments_query.count()

        users_query = query(User)
        users = users_query.count()

        customers = users_query.filter(
            func.lower(User.role).in_(["user", "customer", "client"])
        ).count()

        tickets_query = query(Ticket)
        total_tickets = tickets_query.count()

        open_tickets = tickets_query.filter(
            func.lower(Ticket.status).notin_(
                ["closed", "resolved", "completed"]
            )
        ).count()

        ticket_ids = tickets_query.with_entities(Ticket.id)

        ticket_replies = TicketReply.query.filter(
            TicketReply.ticket_id.in_(ticket_ids)
        ).count()

        conversations = query(Conversation).count()
        chat_messages = ChatMessage.query.join(
            Conversation,
            ChatMessage.conversation_id == Conversation.id,
            isouter=True,
        )

        if organization_id is not None:
            chat_messages = chat_messages.filter(
                Conversation.organization_id == organization_id
            )

        chat_messages = chat_messages.count()

        workflows_query = query(AutomationWorkflow)
        active_workflows = workflows_query.filter(
            AutomationWorkflow.is_active.is_(True)
        ).count()

        execution_query = AutomationExecution.query.join(
            AutomationWorkflow,
            AutomationExecution.workflow_id == AutomationWorkflow.id,
        )

        if organization_id is not None:
            execution_query = execution_query.filter(
                AutomationWorkflow.organization_id == organization_id
            )

        automation_executions = execution_query.count()

        successful_executions = execution_query.filter(
            func.lower(AutomationExecution.status).in_(
                ["completed", "success", "successful"]
            )
        ).count()

        ai_usage_query = query(AIUsage)

        ai_requests = ai_usage_query.with_entities(
            func.coalesce(func.sum(AIUsage.requests), 0)
        ).scalar()

        ai_tokens = ai_usage_query.with_entities(
            func.coalesce(func.sum(AIUsage.tokens), 0)
        ).scalar()

        active_subscriptions = query(Subscription).filter(
            func.lower(Subscription.status) == "active"
        ).count()

        lead_activities = query(LeadActivity).count()

        return BusinessSnapshot(
            organization_id=organization_id,
            organization_name=organization_name,
            leads=int(leads or 0),
            qualified_leads=int(qualified_leads or 0),
            converted_leads=int(converted_leads or 0),
            lost_leads=int(lost_leads or 0),
            pipeline_value=self._money(pipeline_value),
            revenue=self._money(revenue),
            customers=int(customers or 0),
            users=int(users or 0),
            open_tickets=int(open_tickets or 0),
            total_tickets=int(total_tickets or 0),
            ticket_replies=int(ticket_replies or 0),
            conversations=int(conversations or 0),
            chat_messages=int(chat_messages or 0),
            active_workflows=int(active_workflows or 0),
            automation_executions=int(automation_executions or 0),
            successful_executions=int(successful_executions or 0),
            ai_requests=int(ai_requests or 0),
            ai_tokens=int(ai_tokens or 0),
            active_subscriptions=int(active_subscriptions or 0),
            paid_payments=int(paid_payments or 0),
            pending_payments=int(pending_payments or 0),
            lead_activities=int(lead_activities or 0),
        )

    def metrics(
        self,
        organization_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self.snapshot(organization_id).to_dict()
