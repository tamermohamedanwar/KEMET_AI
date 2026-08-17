from app.services.automation_service import automation_service


class ActionRegistry:
    def __init__(self):
        self._actions = {}

    def register(self, name, handler):
        self._actions[name] = handler

    def exists(self, name):
        return name in self._actions

    def get(self, name):
        return self._actions.get(name)

    def execute(self, name, parameters=None, user_id=None):
        handler = self.get(name)

        if not handler:
            return {
                "success": False,
                "message": f"Unknown automation action: {name}",
            }

        try:
            return handler(parameters or {}, user_id=user_id)
        except Exception as exc:
            return {
                "success": False,
                "message": str(exc),
            }


registry = ActionRegistry()


def _create_ticket(parameters, user_id=None):
    return automation_service.create_ticket(
        parameters,
        user_id=user_id,
    )


def _check_order(parameters, user_id=None):
    return automation_service.check_order(parameters)


def _generate_ai_reply(parameters, user_id=None):
    return automation_service.generate_ai_reply(
        parameters or {},
        user_id=user_id,
    )



def _smart_ticket_ai(parameters, user_id=None):
    return automation_service.smart_ticket_ai(
        parameters or {},
        user_id=user_id,
    )


def _send_notification(parameters, user_id=None):
    from app.services.automation_service import automation_service

    return automation_service.send_notification(
        parameters or {},
        user_id=user_id,
    )

registry.register("create_ticket", _create_ticket)
registry.register("check_order", _check_order)
registry.register("generate_ai_reply", _generate_ai_reply)
registry.register("smart_ticket_ai", _smart_ticket_ai)
registry.register("send_notification", _send_notification)

registry.register(
    "classify_ticket",
    lambda parameters, user_id=None:
        automation_service.classify_ticket(parameters, user_id),
)


# Specialized AI automation routes.
# These aliases reuse the existing AI reply engine while preserving
# the specialized route name for workflow routing and analytics.

def _order_tracking(parameters, user_id=None):
    return automation_service.order_tracking(
        parameters or {},
        user_id=user_id,
    )
def _payment_issue(parameters, user_id=None):
    return automation_service.payment_issue(
        parameters or {},
        user_id=user_id,
    )
def _refund_request(parameters, user_id=None):
    return automation_service.refund_request(
        parameters or {},
        user_id=user_id,
    )
def _account_help(parameters, user_id=None):
    return automation_service.account_help(
        parameters or {},
        user_id=user_id,
    )
registry.register("order_tracking", _order_tracking)
registry.register("payment_issue", _payment_issue)
registry.register("refund_request", _refund_request)
registry.register("account_help", _account_help)



registry.register(
    "escalate_ticket",
    lambda parameters, user_id=None:
        automation_service.escalate_ticket(parameters, user_id),
)


registry.register(
    "smart_assignment",
    lambda parameters, user_id=None:
        automation_service.smart_assignment(parameters, user_id),
)


registry.register(
    "sla_management",
    lambda parameters, user_id=None:
        automation_service.sla_management(parameters, user_id),
)


registry.register(
    "auto_follow_up",
    lambda parameters, user_id=None:
        automation_service.auto_follow_up(parameters, user_id),
)

    
registry.register(
    "customer_retention",
    lambda parameters, user_id=None:
        automation_service.customer_retention(parameters, user_id),
)


registry.register(
    "churn_detection",
    lambda parameters, user_id=None:
        automation_service.churn_detection(parameters, user_id),
)


registry.register(
    "lead_scoring",
    lambda parameters, user_id=None:
        automation_service.lead_scoring(parameters, user_id),
)


registry.register(
    "sales_follow_up",
    lambda parameters, user_id=None:
        automation_service.sales_follow_up(parameters, user_id),
)


registry.register(
    "ai_sales_qualification",
    lambda parameters, user_id=None:
        automation_service.ai_sales_qualification(parameters, user_id),
)


registry.register(
    "ai_intent_classifier",
    lambda parameters, user_id=None:
        automation_service.ai_intent_classifier(parameters, user_id),
)


registry.register(
    "customer_lifecycle",
    lambda parameters, user_id=None:
        automation_service.customer_lifecycle(parameters, user_id),
)


registry.register(
    "revenue_opportunity",
    lambda parameters, user_id=None:
        automation_service.revenue_opportunity(parameters, user_id),
)
