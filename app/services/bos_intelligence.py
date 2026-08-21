from datetime import datetime, timedelta

from app import db
from app.models import (
    DemoLead,
    LeadActivity,
    Ticket,
    Subscription,
    Payment,
)
from app.models.automation import (
    AutomationExecution,
    AutomationApproval,
)


class BOSIntelligenceService:
    """
    Read-only intelligence layer for Kemet AI Business OS.

    This service does not execute automations, mutate CRM records,
    approve actions, reject actions, or modify the database.
    It converts existing business data into actionable signals.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @staticmethod
    def _now():
        return datetime.utcnow()

    @staticmethod
    def _safe_count(query):
        try:
            return query.count()
        except Exception:
            return 0

    @classmethod
    def _lead_signals(cls, organization_id):
        signals = []

        if not organization_id:
            return signals

        try:
            leads = (
                DemoLead.query
                .filter(
                    DemoLead.organization_id == organization_id
                )
                .all()
            )
        except Exception:
            return signals

        now = cls._now()

        for lead in leads:
            status = (
                getattr(lead, "status", None)
                or ""
            ).lower()

            score = getattr(lead, "score", None)

            last_activity = None

            try:
                activity = (
                    LeadActivity.query
                    .filter(
                        LeadActivity.lead_id == lead.id
                    )
                    .order_by(
                        LeadActivity.created_at.desc()
                    )
                    .first()
                )

                if activity:
                    last_activity = (
                        getattr(activity, "created_at", None)
                    )
            except Exception:
                last_activity = None

            stale = False

            if last_activity:
                stale = last_activity < (
                    now - timedelta(days=2)
                )

            qualified = status in {
                "qualified",
                "proposal",
                "negotiation",
                "hot",
            }

            if qualified and stale:
                signals.append(
                    {
                        "type": "sales_followup",
                        "priority": cls.HIGH,
                        "title": "Qualified lead needs follow-up",
                        "message": (
                            f"Lead #{lead.id} is in a sales-ready "
                            "stage but has no recent activity."
                        ),
                        "entity": "lead",
                        "entity_id": lead.id,
                        "action": "review_lead",
                    }
                )

            elif qualified:
                signals.append(
                    {
                        "type": "sales_opportunity",
                        "priority": cls.MEDIUM,
                        "title": "Active sales opportunity",
                        "message": (
                            f"Lead #{lead.id} is currently "
                            "in a qualified sales stage."
                        ),
                        "entity": "lead",
                        "entity_id": lead.id,
                        "action": "open_lead",
                    }
                )

        return signals

    @classmethod
    def _support_signals(cls, organization_id):
        signals = []

        if not organization_id:
            return signals

        try:
            tickets = (
                Ticket.query
                .filter(
                    Ticket.organization_id == organization_id,
                    Ticket.status.in_(["open", "pending"]),
                )
                .all()
            )
        except Exception:
            return signals

        for ticket in tickets:
            priority = (
                getattr(ticket, "priority", None)
                or "medium"
            ).lower()

            signal_priority = (
                cls.HIGH
                if priority in {"high", "urgent", "critical"}
                else cls.MEDIUM
            )

            signals.append(
                {
                    "type": "support_attention",
                    "priority": signal_priority,
                    "title": "Support ticket needs attention",
                    "message": (
                        f"Ticket #{ticket.id} is "
                        f"{getattr(ticket, 'status', 'open')}."
                    ),
                    "entity": "ticket",
                    "entity_id": ticket.id,
                    "action": "open_ticket",
                }
            )

        return signals

    @classmethod
    def _automation_signals(cls, organization_id):
        signals = []

        if not organization_id:
            return signals

        try:
            failed = (
                AutomationExecution.query
                .filter(
                    AutomationExecution.organization_id
                    == organization_id,
                    AutomationExecution.status
                    == "failed",
                )
                .order_by(
                    AutomationExecution.created_at.desc()
                )
                .limit(10)
                .all()
            )

            pending = (
                AutomationApproval.query
                .filter(
                    AutomationApproval.organization_id
                    == organization_id,
                    AutomationApproval.status
                    == "pending",
                )
                .order_by(
                    AutomationApproval.created_at.desc()
                )
                .limit(10)
                .all()
            )
        except Exception:
            return signals

        for execution in failed:
            signals.append(
                {
                    "type": "automation_failure",
                    "priority": cls.HIGH,
                    "title": "Automation execution failed",
                    "message": (
                        f"Automation execution #{execution.id} "
                        "requires attention."
                    ),
                    "entity": "automation_execution",
                    "entity_id": execution.id,
                    "action": "review_execution",
                }
            )

        for approval in pending:
            signals.append(
                {
                    "type": "human_review",
                    "priority": cls.HIGH,
                    "title": "Human approval required",
                    "message": (
                        f"Automation approval #{approval.id} "
                        "is waiting for a decision."
                    ),
                    "entity": "automation_approval",
                    "entity_id": approval.id,
                    "action": "review_approval",
                }
            )

        return signals

    @classmethod
    def _business_health(cls, organization_id, signals):
        if not organization_id:
            return 0

        score = 100

        for signal in signals:
            priority = signal.get("priority")

            if priority == cls.HIGH:
                score -= 8
            elif priority == cls.MEDIUM:
                score -= 3
            else:
                score -= 1

        return max(0, min(score, 100))

    @classmethod
    def get_brief(cls, organization_id):
        if not organization_id:
            return {
                "success": True,
                "organization_id": None,
                "health_score": 0,
                "priority_actions": [],
                "summary": "No organization is assigned to this account.",
            }

        sales = cls._lead_signals(organization_id)
        support = cls._support_signals(organization_id)
        automation = cls._automation_signals(organization_id)

        signals = sales + support + automation

        priority_order = {
            cls.HIGH: 0,
            cls.MEDIUM: 1,
            cls.LOW: 2,
        }

        signals.sort(
            key=lambda item: (
                priority_order.get(
                    item.get("priority"),
                    99,
                ),
                item.get("entity_id") or 0,
            )
        )

        high_count = sum(
            1
            for signal in signals
            if signal.get("priority") == cls.HIGH
        )

        medium_count = sum(
            1
            for signal in signals
            if signal.get("priority") == cls.MEDIUM
        )

        health_score = cls._business_health(
            organization_id,
            signals,
        )

        if high_count:
            summary = (
                f"{high_count} high-priority business "
                "actions need attention."
            )
        elif medium_count:
            summary = (
                f"{medium_count} business opportunities "
                "are ready for review."
            )
        else:
            summary = (
                "Business operations are currently "
                "stable."
            )

        return {
            "success": True,
            "organization_id": organization_id,
            "generated_at": cls._now().isoformat(),
            "health_score": health_score,
            "summary": summary,
            "priority_actions": signals[:12],
            "counts": {
                "total": len(signals),
                "high": high_count,
                "medium": medium_count,
                "low": len(signals)
                - high_count
                - medium_count,
                "sales": len(sales),
                "support": len(support),
                "automation": len(automation),
            },
        }
    @classmethod
    def get_decisions(cls, organization_id=None, limit=10):
        """
        Convert BOS business signals into operational decisions.

        This layer is advisory only.
        It does not execute external actions and does not modify the database.
        """

        brief = cls.get_brief(
            organization_id=organization_id
        )

        signals = brief.get("priority_actions", []) or []

        decisions = []

        for index, signal in enumerate(signals[:limit], start=1):
            if not isinstance(signal, dict):
                continue

            signal_type = str(
                signal.get("type", "signal")
            ).lower()

            priority = str(
                signal.get("priority", "low")
            ).lower()

            title = signal.get(
                "title",
                "Business opportunity detected"
            )

            message = signal.get(
                "message",
                ""
            )

            recommended_action = signal.get(
                "recommended_action"
            )

            if not recommended_action:
                if signal_type == "sales":
                    recommended_action = (
                        "Review the lead pipeline and "
                        "prioritize the highest-value opportunities."
                    )

                elif signal_type == "support":
                    recommended_action = (
                        "Review open customer issues and "
                        "resolve the highest-priority cases first."
                    )

                elif signal_type == "automation":
                    recommended_action = (
                        "Review workflow execution history "
                        "and address failed or blocked automations."
                    )

                else:
                    recommended_action = (
                        "Review this business signal and "
                        "determine the appropriate operational response."
                    )

            urgency = {
                "high": 3,
                "medium": 2,
                "low": 1,
            }.get(priority, 1)

            decisions.append({
                "id": index,
                "type": signal_type,
                "priority": priority,
                "urgency": urgency,
                "title": title,
                "reason": message,
                "recommended_action": recommended_action,
                "status": "recommended",
            })

        decisions.sort(
            key=lambda item: (
                item["urgency"],
                item["priority"],
            ),
            reverse=True,
        )

        return {
            "success": True,
            "organization_id": organization_id,
            "generated_at": cls._now().isoformat(),
            "health_score": brief.get("health_score", 0),
            "summary": brief.get("summary", ""),
            "decisions": decisions[:limit],
            "decision_count": len(decisions[:limit]),
        }

    @classmethod
    def get_decision_summary(cls, organization_id=None, limit=10):
        """
        Build an executive decision summary from BOS intelligence.

        Advisory only:
        no external action is executed and no database mutation occurs.
        """
        result = cls.get_decisions(
            organization_id=organization_id,
            limit=limit,
        )

        decisions = result.get("decisions", []) or []

        high = [
            item for item in decisions
            if item.get("priority") == "high"
        ]

        medium = [
            item for item in decisions
            if item.get("priority") == "medium"
        ]

        low = [
            item for item in decisions
            if item.get("priority") == "low"
        ]

        if high:
            executive_message = (
                f"{len(high)} high-priority business "
                "decision(s) require attention."
            )
        elif medium:
            executive_message = (
                f"{len(medium)} medium-priority business "
                "decision(s) should be reviewed."
            )
        elif decisions:
            executive_message = (
                "Business signals are present, but no "
                "urgent decision requires intervention."
            )
        else:
            executive_message = (
                "No strategic decisions currently require attention."
            )

        return {
            "success": True,
            "organization_id": organization_id,
            "generated_at": cls._now().isoformat(),
            "health_score": result.get("health_score", 0),
            "summary": result.get("summary", ""),
            "executive_message": executive_message,
            "decisions": decisions,
            "counts": {
                "total": len(decisions),
                "high": len(high),
                "medium": len(medium),
                "low": len(low),
            },
        }

    @classmethod
    def get_executive_snapshot(cls, organization_id=None, limit=10):
        """
        Build a concise executive snapshot from BOS decision intelligence.

        Advisory only.
        No external action is executed.
        No database mutation occurs.
        """
        result = cls.get_decision_summary(
            organization_id=organization_id,
            limit=limit,
        )

        decisions = result.get("decisions", []) or []
        counts = result.get("counts", {}) or {}

        high = [
            item for item in decisions
            if str(item.get("priority", "")).lower() == "high"
        ]

        medium = [
            item for item in decisions
            if str(item.get("priority", "")).lower() == "medium"
        ]

        top_decisions = []

        for item in decisions[:5]:
            top_decisions.append({
                "id": item.get("id"),
                "type": item.get("type", "signal"),
                "priority": item.get("priority", "low"),
                "title": item.get(
                    "title",
                    "Business decision",
                ),
                "reason": item.get(
                    "reason",
                    "",
                ),
                "recommended_action": item.get(
                    "recommended_action",
                    "Review this business signal.",
                ),
                "status": item.get(
                    "status",
                    "recommended",
                ),
            })

        if high:
            focus = "Immediate executive attention required."
        elif medium:
            focus = "Management review recommended."
        elif decisions:
            focus = "Business signals detected; monitor operations."
        else:
            focus = "Operations currently stable."

        return {
            "success": True,
            "organization_id": organization_id,
            "generated_at": cls._now().isoformat(),
            "health_score": result.get(
                "health_score",
                0,
            ),
            "summary": result.get(
                "summary",
                "",
            ),
            "executive_message": result.get(
                "executive_message",
                "",
            ),
            "focus": focus,
            "counts": {
                "total": counts.get(
                    "total",
                    len(decisions),
                ),
                "high": counts.get(
                    "high",
                    len(high),
                ),
                "medium": counts.get(
                    "medium",
                    len(medium),
                ),
                "low": counts.get(
                    "low",
                    0,
                ),
            },
            "top_decisions": top_decisions,
        }

    @classmethod
    def get_governance_options(cls, organization_id=None, limit=10):
        """
        Return safe governance options for executive decisions.

        Advisory only.
        No external action is executed.
        No database mutation occurs.
        """
        result = cls.get_executive_snapshot(
            organization_id=organization_id,
            limit=limit,
        )

        decisions = result.get("top_decisions", []) or []

        governed = []

        for decision in decisions:
            governed.append({
                "id": decision.get("id"),
                "type": decision.get("type", "signal"),
                "priority": decision.get("priority", "low"),
                "title": decision.get(
                    "title",
                    "Business decision",
                ),
                "reason": decision.get(
                    "reason",
                    "",
                ),
                "recommended_action": decision.get(
                    "recommended_action",
                    "Review this business signal.",
                ),
                "status": "pending_review",
                "allowed_actions": [
                    "approve",
                    "reject",
                    "snooze",
                ],
            })

        return {
            "success": True,
            "organization_id": organization_id,
            "generated_at": cls._now().isoformat(),
            "health_score": result.get(
                "health_score",
                0,
            ),
            "focus": result.get(
                "focus",
                "",
            ),
            "decisions": governed,
            "governance": {
                "mode": "advisory",
                "external_execution": False,
                "database_mutation": False,
                "approval_required": True,
            },
        }

    @classmethod
    def build_approval_preview(
        cls,
        organization_id=None,
        decision_id=None,
    ):
        """
        Build a safe approval preview for one BOS decision.

        This method does not execute an external action.
        This method does not mutate the database.
        """
        result = cls.get_governance_options(
            organization_id=organization_id,
            limit=10,
        )

        decisions = result.get("decisions", []) or []

        selected = None

        for decision in decisions:
            if str(decision.get("id")) == str(decision_id):
                selected = decision
                break

        if selected is None:
            return {
                "success": False,
                "organization_id": organization_id,
                "error": "decision_not_found",
                "message": "The requested business decision was not found.",
            }

        return {
            "success": True,
            "organization_id": organization_id,
            "decision": selected,
            "approval": {
                "status": "pending_approval",
                "approval_required": True,
                "external_execution": False,
                "database_mutation": False,
                "allowed_transitions": [
                    "approve",
                    "reject",
                    "snooze",
                ],
            },
        }

    @classmethod
    def get_approval_transition(cls, decision, transition):
        """
        Validate an approval transition without executing it.

        Advisory-only:
        no external action and no database mutation occur here.
        """
        allowed = {"approve", "reject", "snooze"}

        if transition not in allowed:
            return {
                "success": False,
                "status": "invalid_transition",
                "transition": transition,
                "allowed_transitions": sorted(allowed),
                "approval_required": True,
                "external_execution": False,
                "database_mutation": False,
            }

        if not decision:
            return {
                "success": False,
                "status": "decision_not_found",
                "transition": transition,
                "approval_required": True,
                "external_execution": False,
                "database_mutation": False,
            }

        status_map = {
            "approve": "approved",
            "reject": "rejected",
            "snooze": "snoozed",
        }

        return {
            "success": True,
            "status": status_map[transition],
            "transition": transition,
            "decision": decision,
            "approval_required": True,
            "external_execution": False,
            "database_mutation": False,
            "execution_mode": "advisory",
        }
