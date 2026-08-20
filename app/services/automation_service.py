from app import db
from app.models.ticket import Ticket


class AutomationService:

    def execute(self, action, parameters=None, user_id=None):
        """
        Central dispatcher for automation actions.
        """
        handlers = {
            "check_order": self.check_order,
            "generate_ai_reply": self.generate_ai_reply,
            "smart_ticket_ai": self.smart_ticket_ai,
            "send_notification": self.send_notification,
            "order_tracking": self.order_tracking,
            "payment_issue": self.payment_issue,
            "refund_request": self.refund_request,
            "account_help": self.account_help,
            "classify_ticket": self.classify_ticket,
            "escalate_ticket": self.escalate_ticket,
            "smart_assignment": self.smart_assignment,
            "sla_management": self.sla_management,
            "auto_follow_up": self.auto_follow_up,
            "customer_retention": self.customer_retention,
            "churn_detection": self.churn_detection,
            "lead_scoring": self.lead_scoring,
            "sales_follow_up": self.sales_follow_up,
            "ai_sales_qualification": self.ai_sales_qualification,
            "ai_intent_classifier": self.ai_intent_classifier,
            "customer_lifecycle": self.customer_lifecycle,
            "revenue_opportunity": self.revenue_opportunity,
        }

        handler = handlers.get(action)

        if handler is None:
            raise ValueError(f"Unknown automation action: {action}")

        return handler(parameters or {}, user_id)

    def check_order(self, parameters, user_id=None):
        order_id = parameters.get("order_id")

        return {
            "success": True,
            "action": "check_order",
            "order_id": order_id,
            "status": "processing"
        }

    def generate_ai_reply(self, parameters, user_id=None):
        import json

        parameters = parameters or {}

        message = str(
            parameters.get("message")
            or parameters.get("source_message")
            or ""
        ).strip()

        order_id = str(
            parameters.get("order_id")
            or ""
        ).strip()

        if not message:
            return {
                "success": False,
                "action": "generate_ai_reply",
                "message": "Message is required",
            }

        try:
            from app import db
            from app.models.ticket import Ticket
            from app.models.ticket_reply import TicketReply

            # If the event already provides an order ID, use it.
            # Otherwise ask AI to extract the intended next action.
            if order_id:
                ai_action = "check_order"
                ai_parameters = {
                    "order_id": order_id
                }
            else:
                try:
                    from app.services.ai_service import ask_ai

                    prompt = f"""
Analyze this customer message and return JSON only.

Required format:
{{
  "action": "check_order",
  "parameters": {{
    "order_id": "ORDER-ID"
  }}
}}

If there is no order ID, return:
{{
  "action": "general_reply",
  "parameters": {{}}
}}

Customer message:
{message}

JSON:
"""

                    raw = ask_ai(prompt)

                    parsed = None

                    if isinstance(raw, dict):
                        parsed = raw
                    elif isinstance(raw, str):
                        text = raw.strip()

                        if text.startswith("```"):
                            text = text.replace("```json", "", 1)
                            text = text.replace("```", "", 1).strip()

                        if text.startswith("{") and text.endswith("}"):
                            try:
                                parsed = json.loads(text)
                            except (ValueError, TypeError):
                                parsed = None

                    if not isinstance(parsed, dict):
                        parsed = {
                            "action": "general_reply",
                            "parameters": {}
                        }

                    ai_action = str(
                        parsed.get("action") or "general_reply"
                    ).strip()

                    ai_parameters = parsed.get("parameters") or {}

                except Exception:
                    ai_action = "general_reply"
                    ai_parameters = {}

            action_result = None
            final_reply = ""

            if ai_action == "check_order":
                detected_order_id = str(
                    ai_parameters.get("order_id")
                    or order_id
                    or ""
                ).strip()

                if detected_order_id:
                    action_result = self.check_order({
                        "order_id": detected_order_id
                    })

                    status = action_result.get(
                        "status",
                        "unknown"
                    )

                    final_reply = (
                        f'حالة الطلب {detected_order_id} '
                        f'هي "{status}".'
                    )
                else:
                    ai_action = "general_reply"

            if ai_action != "check_order":
                final_reply = (
                    "تم استلام رسالتك، وسيتم مراجعة طلبك "
                    "والرد عليك في أقرب وقت."
                )

                action_result = {
                    "success": True,
                    "action": "general_reply",
                }

            ticket_id = parameters.get("ticket_id")
            ticket = None

            if ticket_id:
                ticket = Ticket.query.get(ticket_id)

            if ticket is None:
                organization_id = parameters.get(
                    "organization_id"
                )

                if organization_id and user_id:
                    ticket = (
                        Ticket.query
                        .filter_by(
                            organization_id=organization_id,
                            user_id=user_id,
                        )
                        .order_by(Ticket.id.desc())
                        .first()
                    )

            ticket_reply_id = None
            ticket_reply_saved = False
            ticket_reply_deduplicated = False

            if ticket is not None:
                existing_reply = (
                    TicketReply.query
                    .filter_by(
                        ticket_id=ticket.id,
                        message=final_reply,
                    )
                    .order_by(TicketReply.id.desc())
                    .first()
                )

                if existing_reply is not None:
                    ticket_reply_id = existing_reply.id
                    ticket_reply_deduplicated = True
                else:
                    reply = TicketReply(
                        ticket_id=ticket.id,
                        user_id=user_id,
                        message=final_reply,
                        source_message=message,
                        is_staff=False,
                        is_ai=True,
                    )

                    db.session.add(reply)
                    db.session.commit()

                    ticket_reply_id = reply.id
                    ticket_reply_saved = True

            return {
                "success": True,
                "action": "generate_ai_reply",
                "reply": json.dumps(
                    {
                        "action": ai_action,
                        "parameters": ai_parameters,
                    },
                    ensure_ascii=False,
                ),
                "next_action": ai_action,
                "action_result": action_result,
                "final_reply": final_reply,
                "ticket_reply_id": ticket_reply_id,
                "ticket_reply_saved": ticket_reply_saved,
                "ticket_reply_deduplicated": ticket_reply_deduplicated,
            }

        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass

            return {
                "success": False,
                "action": "generate_ai_reply",
                "message": str(exc),
            }

    def smart_ticket_ai(self, parameters, user_id=None):
        import json
        import hashlib

        message = str(parameters.get("message") or "").strip()
        ticket_id = parameters.get("ticket_id")
        organization_id = parameters.get("organization_id")
        user_id = parameters.get("user_id", user_id)

        if not message:
            return {
                "success": False,
                "action": "smart_ticket_ai",
                "message": "Message is required",
            }

        try:
            from app import db
            from app.models.ticket import Ticket
            from app.services.ai_service import ask_ai

            # Stable fingerprint for duplicate prevention.
            normalized_message = " ".join(message.split()).lower()

            hash_source = (
                f"{organization_id or 0}:"
                f"{user_id or 0}:"
                f"{normalized_message}"
            )

            message_hash = hashlib.sha256(
                hash_source.encode("utf-8")
            ).hexdigest()

            # Ask AI for classification/title.
            prompt = f"""
حلل رسالة العميل التالية وأرجع JSON فقط بدون أي نص إضافي.

المطلوب:
- title: عنوان قصير للتذكرة
- priority: واحدة فقط من low, medium, high, urgent
- category: واحدة فقط من order, payment, technical, account, general

رسالة العميل:
{message}

JSON:
"""

            raw = ask_ai(prompt)

            parsed = None

            if isinstance(raw, dict):
                parsed = raw

            elif isinstance(raw, str):
                text = raw.strip()

                if text.startswith("```"):
                    text = text.replace("```json", "", 1)
                    text = text.replace("```", "", 1).strip()

                if text.startswith("{") and text.endswith("}"):
                    try:
                        parsed = json.loads(text)
                    except (ValueError, TypeError):
                        parsed = None

            if not isinstance(parsed, dict):
                return {
                    "success": False,
                    "action": "smart_ticket_ai",
                    "message": "AI returned invalid ticket data",
                }

            title = str(
                parsed.get("title") or "دعم العملاء"
            ).strip()

            priority = str(
                parsed.get("priority") or "medium"
            ).lower().strip()

            category = str(
                parsed.get("category") or "general"
            ).lower().strip()

            allowed_priorities = {
                "low",
                "medium",
                "high",
                "urgent",
            }

            allowed_categories = {
                "order",
                "payment",
                "technical",
                "account",
                "general",
            }

            if priority not in allowed_priorities:
                priority = "medium"

            if category not in allowed_categories:
                category = "general"

            ticket = None
            deduplicated = False

            # Explicit ticket ID has priority.
            if ticket_id:
                ticket = Ticket.query.get(ticket_id)

            # If no explicit ticket was supplied, use message hash.
            if ticket is None and organization_id and user_id:
                ticket = (
                    Ticket.query
                    .filter_by(
                        organization_id=organization_id,
                        user_id=user_id,
                        message_hash=message_hash,
                    )
                    .order_by(Ticket.id.desc())
                    .first()
                )

                if ticket is not None:
                    deduplicated = True

            # Create only when no existing ticket matches.
            if ticket is None:
                if not organization_id or not user_id:
                    return {
                        "success": False,
                        "action": "smart_ticket_ai",
                        "message": (
                            "organization_id and user_id "
                            "are required to create a ticket"
                        ),
                    }

                ticket = Ticket(
                    organization_id=organization_id,
                    user_id=user_id,
                    title=title[:200],
                    status="open",
                    priority=priority,
                    message_hash=message_hash,
                )

                db.session.add(ticket)

            elif not deduplicated and ticket_id:
                # Explicit ticket update.
                ticket.title = title[:200]
                ticket.priority = priority

            db.session.commit()

            return {
                "success": True,
                "action": "smart_ticket_ai",
                "ticket_id": ticket.id,
                "title": ticket.title,
                "priority": ticket.priority,
                "category": category,
                "message_hash": message_hash,
                "deduplicated": deduplicated,
                "message": (
                    "Existing ticket reused"
                    if deduplicated
                    else "Smart ticket processed successfully"
                ),
            }

        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass

            return {
                "success": False,
                "action": "smart_ticket_ai",
                "message": str(exc),
            }


    def _automation_result(
        self,
        action,
        status,
        message="",
        data=None,
        user_id=None,
        requires_human=False,
    ):
        """
        Standard response envelope for automation actions.
        """
        return {
            "success": True,
            "action": action,
            "status": status,
            "message": message,
            "data": data or {},
            "user_id": user_id,
            "requires_human": requires_human,
        }














    def revenue_opportunity(self, parameters, user_id=None):
        """
        Detect commercial opportunities from customer conversations.

        Does not charge, purchase, upgrade, or modify billing records.
        """
        message = (
            parameters.get("message")
            or parameters.get("text")
            or ""
        ).strip()

        lowered = message.lower()

        opportunity = False
        opportunity_type = "none"
        score = 0
        recommended_action = "no_sales_action"
        requires_human = False

        buying_signals = [
            "buy",
            "purchase",
            "upgrade",
            "plan",
            "pricing",
            "price",
            "demo",
            "trial",
            "اشتري",
            "شراء",
            "ترقية",
            "باقة",
            "السعر",
            "تجربة",
            "عرض",
        ]

        upgrade_signals = [
            "upgrade",
            "higher plan",
            "business",
            "enterprise",
            "ترقية",
            "باقة أكبر",
            "باقة اعلى",
            "باقة أعلى",
        ]

        cross_sell_signals = [
            "also need",
            "another product",
            "additional",
            "extra",
            "أحتاج أيضا",
            "احتاج ايضا",
            "منتج آخر",
            "منتج اخر",
            "إضافة",
            "اضافة",
        ]

        if any(signal in lowered for signal in buying_signals):
            opportunity = True
            score = 70
            opportunity_type = "purchase_intent"
            recommended_action = "sales_follow_up"

        if any(signal in lowered for signal in upgrade_signals):
            opportunity = True
            score = max(score, 85)
            opportunity_type = "upgrade"
            recommended_action = "sales_follow_up"

        if any(signal in lowered for signal in cross_sell_signals):
            opportunity = True
            score = max(score, 80)
            opportunity_type = "cross_sell"
            recommended_action = "sales_follow_up"

        if any(signal in lowered for signal in [
            "enterprise",
            "business",
            "شركات",
            "شركة",
        ]):
            score = max(score, 90)
            requires_human = True
            recommended_action = "sales_follow_up"

        if score >= 90:
            priority = "high"
        elif score >= 70:
            priority = "medium"
        else:
            priority = "low"

        return {
            "success": True,
            "action": "revenue_opportunity",
            "status": "opportunity_detected" if opportunity else "no_opportunity",
            "opportunity": opportunity,
            "opportunity_type": opportunity_type,
            "score": score,
            "priority": priority,
            "recommended_action": recommended_action,
            "requires_human": requires_human,
            "message": message,
            "user_id": user_id,
        }

    def customer_lifecycle(self, parameters, user_id=None):
        """
        Determine the customer's lifecycle stage and the next
        recommended automation.
        """
        message = (
            parameters.get("message")
            or parameters.get("text")
            or ""
        ).strip()

        lowered = message.lower()

        stage = "active_customer"
        risk_level = "low"
        recommended_action = "generate_ai_reply"
        requires_human = False

        if any(x in lowered for x in [
            "price",
            "pricing",
            "buy",
            "purchase",
            "demo",
            "trial",
            "السعر",
            "شراء",
            "تجربة",
            "ديمو",
        ]):
            stage = "new_lead"
            risk_level = "low"
            recommended_action = "ai_sales_qualification"

        elif any(x in lowered for x in [
            "cancel",
            "cancellation",
            "إلغاء",
            "الغاء",
            "لا أريد الاستمرار",
        ]):
            stage = "at_risk"
            risk_level = "high"
            recommended_action = "customer_retention"
            requires_human = True

        elif any(x in lowered for x in [
            "not using",
            "inactive",
            "stopped",
            "لم أستخدم",
            "متوقف",
            "متوقف عن الاستخدام",
        ]):
            stage = "at_risk"
            risk_level = "high"
            recommended_action = "customer_retention"

        elif any(x in lowered for x in [
            "refund",
            "استرجاع",
            "استرداد",
            "رد المبلغ",
        ]):
            stage = "churn_risk"
            risk_level = "critical"
            recommended_action = "refund_request"
            requires_human = True

        elif any(x in lowered for x in [
            "thanks",
            "thank you",
            "great",
            "ممتاز",
            "شكرا",
            "شكراً",
        ]):
            stage = "active_customer"
            risk_level = "low"

        return {
            "success": True,
            "action": "customer_lifecycle",
            "status": "lifecycle_classified",
            "stage": stage,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "requires_human": requires_human,
            "message": message,
            "user_id": user_id,
        }

    def ai_intent_classifier(self, parameters, user_id=None):
        """
        Classify customer intent, urgency, sentiment and escalation need.
        Returns structured automation data without modifying records.
        """
        message = (
            parameters.get("message")
            or parameters.get("text")
            or ""
        ).strip()

        lowered = message.lower()

        intent = "general_support"
        priority = "medium"
        customer_type = "unknown"
        sentiment = "neutral"
        requires_human = False
        recommended_action = "generate_ai_reply"
        confidence = 0.70

        if any(x in lowered for x in [
            "refund",
            "استرجاع",
            "استرداد",
            "رد المبلغ",
        ]):
            intent = "refund_request"
            priority = "high"
            recommended_action = "refund_request"
            requires_human = True
            confidence = 0.94

        elif any(x in lowered for x in [
            "payment failed",
            "payment issue",
            "charged",
            "الدفع فشل",
            "فشل الدفع",
            "مشكلة في الدفع",
            "تم خصم المبلغ",
        ]):
            intent = "payment_issue"
            priority = "high"
            recommended_action = "payment_issue"
            requires_human = True
            confidence = 0.95

        elif any(x in lowered for x in [
            "cancel",
            "إلغاء",
            "الغاء",
        ]):
            intent = "cancellation"
            priority = "high"
            recommended_action = "customer_retention"
            confidence = 0.91

        elif any(x in lowered for x in [
            "order",
            "tracking",
            "shipment",
            "delivery",
            "طلب",
            "شحن",
            "توصيل",
            "تتبع",
        ]):
            intent = "order_tracking"
            recommended_action = "order_tracking"
            confidence = 0.93

        elif any(x in lowered for x in [
            "login",
            "password",
            "account",
            "تسجيل الدخول",
            "كلمة المرور",
            "الحساب",
        ]):
            intent = "account_help"
            recommended_action = "account_help"
            confidence = 0.92

        if any(x in lowered for x in [
            "urgent",
            "asap",
            "immediately",
            "عاجل",
            "فورا",
            "فوراً",
        ]):
            priority = "urgent"
            requires_human = True

        if any(x in lowered for x in [
            "angry",
            "terrible",
            "worst",
            "غاضب",
            "سيء",
            "سيئ",
            "كارثة",
            "مستاء",
        ]):
            sentiment = "negative"
            requires_human = True

        if any(x in lowered for x in [
            "thanks",
            "thank you",
            "great",
            "شكرا",
            "شكراً",
            "ممتاز",
        ]):
            sentiment = "positive"

        if any(x in lowered for x in [
            "buy",
            "purchase",
            "pricing",
            "price",
            "اشتري",
            "شراء",
            "السعر",
            "الاسعار",
            "الأسعار",
        ]):
            customer_type = "sales_prospect"
            recommended_action = "ai_sales_qualification"

        return {
            "success": True,
            "action": "ai_intent_classifier",
            "status": "classified",
            "intent": intent,
            "priority": priority,
            "customer_type": customer_type,
            "sentiment": sentiment,
            "requires_human": requires_human,
            "confidence": confidence,
            "recommended_action": recommended_action,
            "message": message,
            "user_id": user_id,
        }

    def ai_sales_qualification(self, parameters, user_id=None):
        """
        Extract structured sales signals from a customer interaction.
        This prepares qualification data without modifying CRM records.
        """
        message = (parameters.get("message") or "").strip()

        purchase_intent = parameters.get("purchase_intent")
        urgency = parameters.get("urgency")
        budget = parameters.get("budget")
        product = parameters.get("product")
        objections = parameters.get("objections")

        if purchase_intent is None:
            purchase_intent = any(
                phrase in message.lower()
                for phrase in (
                    "عايز اشتري",
                    "اريد شراء",
                    "أريد شراء",
                    "سعر",
                    "اشتراك",
                    "شراء",
                    "buy",
                    "purchase",
                    "pricing",
                    "subscribe",
                )
            )

        if urgency is None:
            urgency = "high" if any(
                phrase in message.lower()
                for phrase in (
                    "عاجل",
                    "النهارده",
                    "اليوم",
                    "فورا",
                    "فوراً",
                    "asap",
                    "urgent",
                    "today",
                )
            ) else "normal"

        if objections is None:
            objections = []

            objection_patterns = {
                "price": (
                    "غالي",
                    "السعر",
                    "تكلفة",
                    "expensive",
                    "price",
                    "cost",
                ),
                "trust": (
                    "ضمان",
                    "موثوق",
                    "ثقة",
                    "guarantee",
                    "trust",
                ),
                "features": (
                    "مميزات",
                    "ميزة",
                    "features",
                ),
            }

            for objection, patterns in objection_patterns.items():
                if any(pattern in message.lower() for pattern in patterns):
                    objections.append(objection)

        if purchase_intent:
            sales_stage = "qualified"
            next_action = "sales_follow_up"
        elif message:
            sales_stage = "discovery"
            next_action = "nurture_lead"
        else:
            sales_stage = "unknown"
            next_action = "request_information"

        return {
            "success": True,
            "action": "ai_sales_qualification",
            "status": "sales_qualification_completed",
            "purchase_intent": bool(purchase_intent),
            "urgency": urgency,
            "budget": budget,
            "product": product,
            "objections": objections,
            "sales_stage": sales_stage,
            "next_action": next_action,
            "message": message,
            "user_id": user_id,
            "crm_updated": False,
            "requires_human": sales_stage == "qualified",
        }

    def sales_follow_up(self, parameters, user_id=None):
        """
        Create a CRM sales follow-up activity.

        This action does not send email, WhatsApp, SMS, or payment requests.
        It creates a follow-up task for the sales team.
        """
        from datetime import datetime, timedelta

        from app import db
        from app.models.demo_lead import DemoLead
        from app.models.lead_activity import LeadActivity

        parameters = parameters or {}

        lead_id = parameters.get("lead_id")

        if not lead_id:
            return {
                "success": False,
                "action": "sales_follow_up",
                "status": "missing_lead",
                "message": "lead_id is required",
                "user_id": user_id,
            }

        try:
            lead_id = int(lead_id)
        except (TypeError, ValueError):
            return {
                "success": False,
                "action": "sales_follow_up",
                "status": "invalid_lead",
                "message": "Invalid lead_id",
                "user_id": user_id,
            }

        lead = DemoLead.query.filter(
            DemoLead.id == lead_id
        ).first()

        if lead is None:
            return {
                "success": False,
                "action": "sales_follow_up",
                "status": "lead_not_found",
                "message": "Lead not found",
                "lead_id": lead_id,
                "user_id": user_id,
            }

        lead_status = (
            parameters.get("lead_status")
            or parameters.get("status")
            or getattr(lead, "status", None)
            or "warm"
        ).strip().lower()

        score = parameters.get(
            "score",
            getattr(lead, "lead_score", 0) or 0,
        )

        try:
            score = int(score or 0)
        except (TypeError, ValueError):
            score = 0

        message = (
            parameters.get("message")
            or parameters.get("content")
            or ""
        ).strip()

        follow_up_plan = {
            "qualified": {
                "priority": "critical",
                "channel": "sales_team",
                "timing": "immediate",
                "action": "contact_lead",
                "hours": 0,
            },
            "hot": {
                "priority": "high",
                "channel": "sales_team",
                "timing": "within_1_hour",
                "action": "contact_lead",
                "hours": 1,
            },
            "warm": {
                "priority": "medium",
                "channel": "sales_nurturing",
                "timing": "within_24_hours",
                "action": "nurture_lead",
                "hours": 24,
            },
            "cold": {
                "priority": "low",
                "channel": "marketing",
                "timing": "scheduled",
                "action": "monitor_lead",
                "hours": 72,
            },
        }

        plan = follow_up_plan.get(
            lead_status,
            follow_up_plan["warm"],
        )

        now = datetime.utcnow()

        if plan["hours"] == 0:
            due_at = now
        else:
            due_at = now + timedelta(hours=plan["hours"])

        existing = LeadActivity.query.filter(
            LeadActivity.lead_id == lead.id,
            LeadActivity.activity_type == "follow_up",
            LeadActivity.completed_at.is_(None),
            LeadActivity.due_at.isnot(None),
        ).first()

        if existing:
            return {
                "success": True,
                "action": "sales_follow_up",
                "status": "already_scheduled",
                "lead_id": lead.id,
                "activity_id": existing.id,
                "due_at": existing.due_at.isoformat(),
                "lead_status": lead_status,
                "score": score,
                "priority": plan["priority"],
                "channel": plan["channel"],
                "timing": plan["timing"],
                "next_action": plan["action"],
                "message_sent": False,
                "requires_human": True,
                "user_id": user_id,
            }

        activity = LeadActivity(
            organization_id=lead.organization_id,
            lead_id=lead.id,
            user_id=user_id,
            activity_type="follow_up",
            subject="Sales follow-up",
            content=message or (
                f"Sales follow-up for {lead.company_name} "
                f"({lead_status}, score {score})"
            ),
            due_at=due_at,
        )

        db.session.add(activity)

        lead.next_follow_up_at = due_at

        db.session.commit()

        return {
            "success": True,
            "action": "sales_follow_up",
            "status": "follow_up_scheduled",
            "lead_id": lead.id,
            "activity_id": activity.id,
            "due_at": due_at.isoformat(),
            "lead_status": lead_status,
            "score": score,
            "priority": plan["priority"],
            "channel": plan["channel"],
            "timing": plan["timing"],
            "next_action": plan["action"],
            "message": message,
            "message_sent": False,
            "requires_human": True,
            "user_id": user_id,
        }

    def lead_scoring(self, parameters, user_id=None):
        """
        Score a sales lead using available interaction signals.
        Does not modify lead records.
        """
        message = (parameters.get("message") or "").strip()

        priority = (
            parameters.get("priority")
            or parameters.get("ticket_priority")
            or "medium"
        ).strip().lower()

        purchase_intent = parameters.get("purchase_intent", False)
        interaction_count = parameters.get("interaction_count", 0)
        deal_value = parameters.get("deal_value", 0)
        interested = parameters.get("interested", False)

        try:
            interaction_count = int(interaction_count or 0)
        except (TypeError, ValueError):
            interaction_count = 0

        try:
            deal_value = float(deal_value or 0)
        except (TypeError, ValueError):
            deal_value = 0

        score = 0

        priority_scores = {
            "low": 5,
            "medium": 15,
            "high": 25,
            "urgent": 30,
            "critical": 30,
        }

        score += priority_scores.get(priority, 15)

        if purchase_intent:
            score += 30

        if interested:
            score += 20

        score += min(interaction_count * 5, 15)

        if deal_value >= 10000:
            score += 20
        elif deal_value >= 5000:
            score += 15
        elif deal_value >= 1000:
            score += 10
        elif deal_value > 0:
            score += 5

        score = min(score, 100)

        if score >= 75:
            lead_status = "qualified"
        elif score >= 50:
            lead_status = "hot"
        elif score >= 25:
            lead_status = "warm"
        else:
            lead_status = "cold"

        if lead_status in ("qualified", "hot"):
            next_action = "sales_follow_up"
        elif lead_status == "warm":
            next_action = "nurture_lead"
        else:
            next_action = "monitor_lead"

        return {
            "success": True,
            "action": "lead_scoring",
            "status": "lead_scored",
            "score": score,
            "lead_status": lead_status,
            "priority": priority,
            "purchase_intent": bool(purchase_intent),
            "interaction_count": interaction_count,
            "deal_value": deal_value,
            "next_action": next_action,
            "message": message,
            "user_id": user_id,
            "requires_human": lead_status == "qualified",
        }

    def churn_detection(self, parameters, user_id=None):
        """
        Detect potential customer churn from available interaction signals.
        Does not modify customer records.
        """
        message = (parameters.get("message") or "").strip()

        priority = (
            parameters.get("priority")
            or parameters.get("ticket_priority")
            or "medium"
        ).strip().lower()

        inactivity_days = parameters.get("inactivity_days")
        negative_signals = parameters.get("negative_signals", 0)

        try:
            inactivity_days = int(inactivity_days or 0)
        except (TypeError, ValueError):
            inactivity_days = 0

        try:
            negative_signals = int(negative_signals or 0)
        except (TypeError, ValueError):
            negative_signals = 0

        score = 0

        if inactivity_days >= 30:
            score += 50
        elif inactivity_days >= 14:
            score += 30
        elif inactivity_days >= 7:
            score += 15

        score += min(negative_signals * 15, 45)

        if priority in ("urgent", "critical"):
            score += 20
        elif priority == "high":
            score += 10

        score = min(score, 100)

        if score >= 70:
            risk_level = "critical"
        elif score >= 45:
            risk_level = "high"
        elif score >= 20:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "success": True,
            "action": "churn_detection",
            "status": "churn_risk_detected",
            "churn_score": score,
            "risk_level": risk_level,
            "inactivity_days": inactivity_days,
            "negative_signals": negative_signals,
            "message": message,
            "user_id": user_id,
            "next_action": (
                "customer_retention"
                if risk_level in ("high", "critical")
                else "monitor_customer"
            ),
            "requires_human": risk_level == "critical",
        }

    def customer_retention(self, parameters, user_id=None):
        """
        Identify customers who may need retention-focused follow-up.
        Does not modify customer records.
        """
        message = (parameters.get("message") or "").strip()

        priority = (
            parameters.get("priority")
            or parameters.get("ticket_priority")
            or "medium"
        ).strip().lower()

        reason = (
            parameters.get("reason")
            or parameters.get("retention_reason")
            or "customer_follow_up"
        )

        retention_priority = {
            "low": "normal",
            "medium": "important",
            "high": "high",
            "urgent": "critical",
            "critical": "critical",
        }.get(priority, "important")

        return {
            "success": True,
            "action": "customer_retention",
            "status": "retention_follow_up_required",
            "priority": retention_priority,
            "reason": reason,
            "message": message,
            "user_id": user_id,
            "next_action": "prepare_retention_follow_up",
            "requires_human": priority in ("high", "urgent", "critical"),
        }

    def auto_follow_up(self, parameters, user_id=None):
        """
        Prepare an automatic customer follow-up decision.
        Does not send a message or modify customer records.
        """
        message = (parameters.get("message") or "").strip()
        status = (parameters.get("status") or "").strip().lower()
        priority = (
            parameters.get("priority")
            or parameters.get("ticket_priority")
            or "medium"
        ).strip().lower()

        unresolved_statuses = {
            "open",
            "pending",
            "waiting",
            "in_progress",
            "unresolved",
        }

        needs_follow_up = status in unresolved_statuses

        follow_up_hours = {
            "urgent": 2,
            "critical": 2,
            "high": 4,
            "medium": 12,
            "low": 24,
        }.get(priority, 12)

        return {
            "success": True,
            "action": "auto_follow_up",
            "status": (
                "follow_up_required"
                if needs_follow_up
                else "no_follow_up"
            ),
            "needs_follow_up": needs_follow_up,
            "follow_up_hours": follow_up_hours if needs_follow_up else None,
            "priority": priority,
            "ticket_status": status,
            "message": message,
            "user_id": user_id,
        }

    def sla_management(self, parameters, user_id=None):
        """
        Calculate an SLA target based on ticket priority and escalation state.
        Does not modify ticket records.
        """
        priority = (
            parameters.get("priority")
            or parameters.get("ticket_priority")
            or "medium"
        ).strip().lower()

        requires_human = bool(
            parameters.get("requires_human", False)
        )

        sla_hours = {
            "low": 24,
            "medium": 8,
            "high": 4,
            "urgent": 1,
            "critical": 1,
        }.get(priority, 8)

        if requires_human:
            sla_hours = min(sla_hours, 2)

        return {
            "success": True,
            "action": "sla_management",
            "status": "sla_calculated",
            "priority": priority,
            "sla_hours": sla_hours,
            "requires_human": requires_human,
            "user_id": user_id,
        }

    def smart_assignment(self, parameters, user_id=None):
        """
        Select the most appropriate support queue for a request.
        This action only returns an assignment decision.
        """
        message = (parameters.get("message") or "").strip().lower()
        category = (parameters.get("category") or "").strip().lower()

        queue = "general_support"

        if category == "payment" or any(x in message for x in [
            "payment",
            "دفع",
            "خصم",
            "فاتورة",
            "transaction",
        ]):
            queue = "billing"

        elif category == "refund" or any(x in message for x in [
            "refund",
            "استرجاع",
            "استرداد",
            "رد المبلغ",
        ]):
            queue = "refunds"

        elif category == "order" or any(x in message for x in [
            "order",
            "طلب",
            "شحنة",
            "شحن",
            "توصيل",
            "tracking",
        ]):
            queue = "orders"

        elif category == "account" or any(x in message for x in [
            "login",
            "password",
            "account",
            "تسجيل الدخول",
            "كلمة المرور",
            "الحساب",
        ]):
            queue = "account_support"

        return {
            "success": True,
            "action": "smart_assignment",
            "status": "assigned",
            "queue": queue,
            "message": message,
            "user_id": user_id,
        }

    def escalate_ticket(self, parameters, user_id=None):
        """
        Decide whether a support request requires human escalation.
        No ticket mutation is performed here.
        """
        message = (parameters.get("message") or "").strip().lower()

        escalation_terms = [
            "urgent",
            "emergency",
            "complaint",
            "شكوى",
            "عاجل",
            "فوري",
            "مشكلة كبيرة",
            "فشل الدفع",
            "تم خصم المبلغ",
            "refund",
            "استرجاع",
        ]

        requires_human = any(
            term in message
            for term in escalation_terms
        )

        return {
            "success": True,
            "action": "escalate_ticket",
            "status": "escalated" if requires_human else "no_escalation",
            "requires_human": requires_human,
            "message": message,
            "user_id": user_id,
        }

    def classify_ticket(self, parameters, user_id=None):
        """
        Classify a support request into a structured category and priority.
        Does not modify the ticket directly.
        """
        message = (parameters.get("message") or "").strip().lower()

        category = "general_support"
        priority = "medium"

        if any(x in message for x in [
            "refund", "استرجاع", "استرداد", "رد المبلغ"
        ]):
            category = "refund"

        elif any(x in message for x in [
            "payment", "دفع", "خصم", "فاتورة"
        ]):
            category = "payment"

        elif any(x in message for x in [
            "order", "طلب", "شحنة", "شحن", "توصيل", "tracking"
        ]):
            category = "order"

        elif any(x in message for x in [
            "login", "password", "account", "تسجيل الدخول",
            "كلمة المرور", "الحساب"
        ]):
            category = "account"

        if any(x in message for x in [
            "urgent", "emergency", "عاجل", "فوري", "مشكلة كبيرة"
        ]):
            priority = "high"

        return {
            "success": True,
            "action": "classify_ticket",
            "status": "classified",
            "category": category,
            "priority": priority,
            "message": message,
            "user_id": user_id,
        }

    def order_tracking(self, parameters, user_id=None):
        """
        Track an order/payment-related request using existing Kemet AI data.
        Payment records are tenant-scoped by organization_id.
        """
        from app.models import Payment

        parameters = parameters or {}

        organization_id = parameters.get("organization_id")
        message = str(parameters.get("message") or "").strip()
        payment_id = parameters.get("payment_id")
        transaction_id = parameters.get("transaction_id")

        query = Payment.query

        if organization_id is not None:
            query = query.filter_by(
                organization_id=organization_id
            )

        payment = None

        if payment_id:
            payment = query.filter_by(
                id=payment_id
            ).first()

        if payment is None and transaction_id:
            payment = query.filter_by(
                provider_transaction_id=str(transaction_id)
            ).first()

        if payment is None and organization_id is not None:
            payment = (
                query
                .order_by(Payment.id.desc())
                .first()
            )

        if payment is None:
            return {
                "success": True,
                "action": "order_tracking",
                "status": "not_found",
                "message": message,
                "payment_id": payment_id,
                "transaction_id": transaction_id,
                "result": "No matching payment/order record found.",
            }

        return {
            "success": True,
            "action": "order_tracking",
            "status": "found",
            "payment_id": payment.id,
            "transaction_id": getattr(
                payment,
                "provider_transaction_id",
                None,
            ),
            "payment_status": getattr(
                payment,
                "status",
                None,
            ),
            "amount": getattr(
                payment,
                "amount",
                None,
            ),
            "currency": getattr(
                payment,
                "currency",
                None,
            ),
            "message": message,
        }

    def payment_issue(self, parameters, user_id=None):
        """Handle payment issues with deterministic payment inspection."""
        parameters = parameters or {}

        message = (parameters.get("message") or "").strip()
        payment_id = parameters.get("payment_id")
        transaction_id = parameters.get("transaction_id")

        from app.models import Payment

        payment = None

        if payment_id:
            payment = Payment.query.filter_by(id=payment_id).first()

        if payment is None and transaction_id:
            payment = Payment.query.filter_by(
                provider_transaction_id=str(transaction_id)
            ).first()

        if payment is None:
            payment = (
                Payment.query
                .filter_by(organization_id=parameters.get("organization_id"))
                .order_by(Payment.id.desc())
                .first()
            )

        if payment is None:
            return {
                "success": True,
                "action": "payment_issue",
                "status": "payment_not_found",
                "message": message,
                "payment_id": payment_id,
                "transaction_id": transaction_id,
                "requires_human": True,
                "recommended_action": "payment_review",
            }

        return {
            "success": True,
            "action": "payment_issue",
            "status": "payment_found",
            "payment_id": payment.id,
            "transaction_id": getattr(payment, "transaction_id", None),
            "payment_status": getattr(payment, "status", None),
            "amount": getattr(payment, "amount", None),
            "currency": getattr(payment, "currency", None),
            "message": message,
            "requires_human": True,
            "recommended_action": "payment_review",
        }

    def refund_request(self, parameters, user_id=None):
        """Create or execute a refund request with explicit approval."""
        parameters = parameters or {}
        approved_execution = (
            parameters.get("_approved_execution") is True
        )

        message = (parameters.get("message") or "").strip()
        payment_id = parameters.get("payment_id")
        transaction_id = parameters.get("transaction_id")

        from app.models import Payment

        payment = None

        if payment_id:
            payment = Payment.query.filter_by(
                id=payment_id
            ).first()

        if payment is None and transaction_id:
            payment = Payment.query.filter_by(
                provider_transaction_id=str(transaction_id)
            ).first()

        if payment is None:
            organization_id = parameters.get("organization_id")

            if organization_id:
                payment = (
                    Payment.query
                    .filter_by(organization_id=organization_id)
                    .order_by(Payment.id.desc())
                    .first()
                )

        if payment is None:
            return {
                "success": True,
                "action": "refund_request",
                "status": "manual_review_required",
                "message": message,
                "reason": "Payment record not found.",
                "approval_required": True,
                "financial_action_executed": False,
                "requires_human": True,
                "recommended_action": "refund_review",
            }

        if not approved_execution:
            return {
                "success": True,
                "action": "refund_request",
                "status": "manual_review_required",
                "payment_id": payment.id,
                "transaction_id": getattr(
                    payment,
                    "provider_transaction_id",
                    None,
                ),
                "payment_status": getattr(
                    payment,
                    "status",
                    None,
                ),
                "amount": getattr(
                    payment,
                    "amount",
                    None,
                ),
                "currency": getattr(
                    payment,
                    "currency",
                    None,
                ),
                "message": message,
                "approval_required": True,
                "financial_action_executed": False,
                "requires_human": True,
                "recommended_action": "refund_review",
            }

        # Production-safe dry run: never contacts Paymob.
        if parameters.get("_dry_run") is True:
            return {
                "success": True,
                "action": "refund_request",
                "status": "dry_run_completed",
                "payment_id": payment.id,
                "transaction_id": getattr(
                    payment,
                    "provider_transaction_id",
                    None,
                ),
                "payment_status": getattr(
                    payment,
                    "status",
                    None,
                ),
                "amount": getattr(
                    payment,
                    "amount",
                    None,
                ),
                "currency": getattr(
                    payment,
                    "currency",
                    None,
                ),
                "message": message,
                "approval_required": False,
                "financial_action_executed": False,
                "requires_human": False,
                "recommended_action": "refund_would_be_processed",
                "dry_run": True,
            }

        from app.services.payment_service import refund_payment

        try:
            refund_result = refund_payment(
                payment,
                amount=parameters.get("amount"),
            )

            return {
                "success": True,
                "action": "refund_request",
                "status": "completed",
                "payment_id": payment.id,
                "transaction_id": getattr(
                    payment,
                    "provider_transaction_id",
                    None,
                ),
                "payment_status": getattr(
                    payment,
                    "status",
                    None,
                ),
                "amount": getattr(
                    payment,
                    "amount",
                    None,
                ),
                "currency": getattr(
                    payment,
                    "currency",
                    None,
                ),
                "message": message,
                "approval_required": False,
                "financial_action_executed": True,
                "requires_human": False,
                "recommended_action": "refund_processed",
                "provider_response": refund_result,
            }

        except Exception as exc:
            return {
                "success": False,
                "action": "refund_request",
                "status": "refund_failed",
                "payment_id": payment.id,
                "transaction_id": getattr(
                    payment,
                    "provider_transaction_id",
                    None,
                ),
                "payment_status": getattr(
                    payment,
                    "status",
                    None,
                ),
                "amount": getattr(
                    payment,
                    "amount",
                    None,
                ),
                "currency": getattr(
                    payment,
                    "currency",
                    None,
                ),
                "message": message,
                "approval_required": False,
                "financial_action_executed": False,
                "requires_human": True,
                "recommended_action": "refund_retry_or_review",
                "error": str(exc),
            }

    def account_help(self, parameters, user_id=None):
        """Inspect the user account without modifying credentials."""
        parameters = parameters or {}

        message = (parameters.get("message") or "").strip()
        requested_user_id = parameters.get("user_id") or user_id

        from app.models import User

        user = None

        if requested_user_id:
            user = User.query.filter_by(id=requested_user_id).first()

        if user is None:
            return {
                "success": True,
                "action": "account_help",
                "status": "user_not_found",
                "user_id": requested_user_id,
                "message": message,
                "requires_human": True,
                "recommended_action": "account_review",
            }

        return {
            "success": True,
            "action": "account_help",
            "status": "user_found",
            "user_id": user.id,
            "email": getattr(user, "email", None),
            "message": message,
            "credentials_modified": False,
            "requires_human": False,
            "recommended_action": "account_assistance",
        }

    def send_notification(self, parameters, user_id=None):
        from app import db
        from app.models.notification import Notification
        from app.models.user import User

        parameters = parameters or {}

        title = (
            parameters.get("title")
            or "Kemet AI Notification"
        )

        message = (
            parameters.get("message")
            or ""
        ).strip()

        if not message:
            return {
                "success": False,
                "action": "send_notification",
                "message": "Notification message is required",
                "status": "failed",
            }

        user = None

        if user_id is not None:
            user = User.query.filter_by(id=user_id).first()

        organization_id = (
            user.organization_id
            if user is not None
            else parameters.get("organization_id")
        )

        # Notification deduplication:
        # Do not create the same internal notification more than once
        # for the same tenant/user/content.
        existing = (
            Notification.query
            .filter_by(
                organization_id=organization_id,
                user_id=user_id,
                title=title,
                message=message,
                channel="internal",
            )
            .order_by(Notification.id.desc())
            .first()
        )

        if existing is not None:
            return {
                "success": True,
                "action": "send_notification",
                "notification_id": existing.id,
                "title": existing.title,
                "message": existing.message,
                "user_id": existing.user_id,
                "organization_id": existing.organization_id,
                "channel": existing.channel,
                "status": existing.status,
                "deduplicated": True,
                "message": existing.message,
                "dedupe_message": "Existing notification reused",
            }

        notification = Notification(
            organization_id=organization_id,
            user_id=user_id,
            title=title,
            message=message,
            channel="internal",
            status="sent",
            is_read=False,
        )

        db.session.add(notification)
        db.session.commit()

        return {
            "success": True,
            "action": "send_notification",
            "notification_id": notification.id,
            "title": title,
            "message": message,
            "user_id": user_id,
            "organization_id": organization_id,
            "channel": "internal",
            "status": "sent",
            "deduplicated": False,
        }

    def create_ticket(self, parameters, user_id=None):
        title = parameters.get(
            "title",
            "طلب دعم جديد"
        )

        from app.models.user import User

        user = User.query.filter_by(id=user_id).first()

        if not user:
            return {
                "success": False,
                "message": "User not found"
            }

        if not user.organization_id:
            return {
                "success": False,
                "message": "User has no organization"
            }

        ticket = Ticket(
            title=title,
            user_id=user_id,
            organization_id=user.organization_id,
            status="open"
        )

        db.session.add(ticket)
        db.session.commit()

        return {
            "success": True,
            "action": "create_ticket",
            "ticket_id": ticket.id,
            "message": f"تم إنشاء تذكرة دعم بنجاح. رقم التذكرة: #{ticket.id}"
        }


automation_service = AutomationService()
