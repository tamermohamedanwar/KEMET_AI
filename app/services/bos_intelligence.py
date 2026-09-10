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


_SAFE_BOS_ACTIONS = {
    "lead_scoring": "Find my hottest leads",
    "churn_detection": "Find customers at risk of churn",
    "revenue_opportunity": "Find revenue opportunities",
    "customer_retention": "Retain customers at risk",
    "ai_sales_qualification": "Qualify sales leads",
    "payment_issue": "Review payment issues",
    "account_help": "Review account issues",
    "sales_follow_up": "Follow up with customers",
    "order_tracking": "Track order",
    "create_ticket": "Create support ticket",
    "smart_ticket_ai": "Review support tickets",
    "send_notification": "Send business notification",
    "refund_request": "Process refund request",
}

def _safe_executable_action(signal_type):
    mapping = {
        "lead": "lead_scoring",
        "leads": "lead_scoring",
        "lead_scoring": "lead_scoring",
        "churn": "churn_detection",
        "churn_detection": "churn_detection",
        "retention": "customer_retention",
        "customer_retention": "customer_retention",
        "revenue": "revenue_opportunity",
        "revenue_opportunity": "revenue_opportunity",
        "sales": "sales_follow_up",
        "sales_follow_up": "sales_follow_up",
        "follow_up": "sales_follow_up",
        "order": "order_tracking",
        "order_tracking": "order_tracking",
        "payment": "payment_issue",
        "payment_issue": "payment_issue",
        "account": "account_help",
        "account_help": "account_help",
        "support": "smart_ticket_ai",
        "support_attention": "smart_ticket_ai",
        "ticket": "smart_ticket_ai",
        "smart_ticket_ai": "smart_ticket_ai",
        "qualification": "ai_sales_qualification",
        "ai_sales_qualification": "ai_sales_qualification",
    }

    key = str(signal_type or "").strip().lower()

    if key in mapping:
        return mapping[key]

    signal_parts = {
        part
        for part in key.replace("-", "_").split("_")
        if part
    }

    if "support" in signal_parts or "ticket" in signal_parts:
        return "smart_ticket_ai"

    if "churn" in signal_parts:
        return "churn_detection"

    if "retention" in signal_parts:
        return "customer_retention"

    if "revenue" in signal_parts:
        return "revenue_opportunity"

    if "lead" in signal_parts:
        return "lead_scoring"

    if "payment" in signal_parts:
        return "payment_issue"

    if "account" in signal_parts:
        return "account_help"

    if "order" in signal_parts:
        return "order_tracking"

    if "follow" in signal_parts or "sales" in signal_parts:
        return "sales_follow_up"

    return None


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

        signals = signals or []

        if not signals:
            return 100

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

        total = len(signals)

        high_ratio = high_count / total
        medium_ratio = medium_count / total

        high_penalty = min(high_ratio * 50, 50)
        medium_penalty = min(medium_ratio * 20, 20)

        score = 100 - high_penalty - medium_penalty

        return round(max(0, min(score, 100)), 2)

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

            impact = {
                "high": 3,
                "medium": 2,
                "low": 1,
            }.get(priority, 1)

            confidence = 0.95 if signal_type in {
                "sales",
                "support",
                "support_attention",
                "automation",
                "automation_attention",
                "human_review",
            } else 0.75

            entity_id = signal.get("entity_id")
            decision_id = signal.get("decision_id")
            if not decision_id:
                decision_id = (
                    f"kemet-bos-{signal_type}-"
                    f"{entity_id or 'global'}-{priority}"
                )

            if priority == "high":
                why_now = (
                    "This signal has high operational priority "
                    "and should be reviewed immediately."
                )
                expected_outcome = (
                    "Reduce operational risk and resolve the "
                    "highest-priority business issue."
                )
            elif priority == "medium":
                why_now = (
                    "This signal represents a meaningful business "
                    "opportunity or operational risk."
                )
                expected_outcome = (
                    "Improve operational performance by addressing "
                    "the issue before it becomes critical."
                )
            else:
                why_now = (
                    "This signal is currently low priority but "
                    "should remain visible for monitoring."
                )
                expected_outcome = (
                    "Maintain operational stability and prevent "
                    "future escalation."
                )

            decision_score = round(
                (impact * 40)
                + (urgency * 35)
                + (confidence * 25),
                2,
            )

            decisions.append({
                "id": decision_id,
                "decision_id": decision_id,
                "index": index,
                "type": signal_type,
                "priority": priority,
                "urgency": urgency,
                "impact": impact,
                "confidence": confidence,
                "decision_score": decision_score,
                "entity_id": entity_id,
                "title": title,
                "reason": message,
                "why_now": why_now,
                "recommended_action": recommended_action,
                "action": _safe_executable_action(signal_type),
                "executable_action": _safe_executable_action(signal_type),
                "expected_outcome": expected_outcome,
                "status": "recommended",
            })

        decisions.sort(
            key=lambda item: (
                item.get("decision_score", 0),
                item.get("urgency", 0),
                item.get("impact", 0),
            ),
            reverse=True,
        )

        # Prefer decision diversity when multiple signal types exist.
        diversified = []
        deferred = []

        for decision in decisions:
            if len(diversified) < limit:
                current_type = decision.get("type")
                existing_types = {
                    item.get("type")
                    for item in diversified
                }

                if (
                    current_type not in existing_types
                    or len(existing_types) == 1
                ):
                    diversified.append(decision)
                else:
                    deferred.append(decision)
            else:
                deferred.append(decision)

        if len(diversified) < min(limit, len(decisions)):
            for decision in deferred:
                if decision not in diversified:
                    diversified.append(decision)

                if len(diversified) >= limit:
                    break

        decisions = diversified

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
            item
            for item in decisions
            if str(item.get("priority", "")).lower() == "high"
        ]

        medium = [
            item
            for item in decisions
            if str(item.get("priority", "")).lower() == "medium"
        ]

        top_decisions = []

        for item in decisions[:5]:
            decision_id = (
                item.get("decision_id")
                or item.get("id")
            )

            action = (
                item.get("action")
                or item.get("executable_action")
            )

            top_decisions.append({
                "id": decision_id,
                "decision_id": decision_id,
                "type": item.get(
                    "type",
                    "signal",
                ),
                "priority": item.get(
                    "priority",
                    "low",
                ),
                "urgency": item.get(
                    "urgency",
                    1,
                ),
                "impact": item.get(
                    "impact",
                    1,
                ),
                "confidence": item.get(
                    "confidence",
                    0,
                ),
                "decision_score": item.get(
                    "decision_score",
                    0,
                ),
                "entity_id": item.get(
                    "entity_id",
                ),
                "title": item.get(
                    "title",
                    "Business decision",
                ),
                "reason": item.get(
                    "reason",
                    "",
                ),
                "why_now": item.get(
                    "why_now",
                    "",
                ),
                "recommended_action": item.get(
                    "recommended_action",
                    "Review this business signal.",
                ),
                "action": action,
                "executable_action": action,
                "expected_outcome": item.get(
                    "expected_outcome",
                    "",
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
            "decisions": top_decisions,
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

        decisions = (
            result.get("decisions")
            or result.get("top_decisions")
            or []
        )

        governed = []

        for decision in decisions:
            decision_id = (
                decision.get("decision_id")
                or decision.get("id")
            )

            action = (
                decision.get("action")
                or decision.get("executable_action")
            )

            governed.append({
                "id": decision_id,
                "decision_id": decision_id,
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
                "action": action,
                "executable_action": action,
                "expected_outcome": decision.get(
                    "expected_outcome",
                    "",
                ),
                "confidence": decision.get(
                    "confidence",
                    0,
                ),
                "impact": decision.get(
                    "impact",
                    0,
                ),
                "urgency": decision.get(
                    "urgency",
                    "normal",
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
            candidate_id = (
                decision.get("decision_id")
                or decision.get("id")
            )
            if str(candidate_id) == str(decision_id):
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

        # Advisory-only guard:
        # A real decision object is required before a transition
        # can be considered valid. Numeric IDs alone are not decisions.
        if decision is None:
            return {
                "success": False,
                "status": "decision_not_found",
                "transition": transition,
                "approval_required": True,
                "external_execution": False,
                "database_mutation": False,
            }

        if isinstance(decision, bool):
            return {
                "success": False,
                "status": "decision_not_found",
                "transition": transition,
                "approval_required": True,
                "external_execution": False,
                "database_mutation": False,
            }

        if isinstance(decision, int):
            return {
                "success": False,
                "status": "decision_not_found",
                "transition": transition,
                "approval_required": True,
                "external_execution": False,
                "database_mutation": False,
            }

        if isinstance(decision, str):
            if not decision.strip():
                return {
                    "success": False,
                    "status": "decision_not_found",
                    "transition": transition,
                    "approval_required": True,
                    "external_execution": False,
                    "database_mutation": False,
                }

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
