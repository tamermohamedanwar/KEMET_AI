from app.services.automation_service import automation_service


class ActionRegistry:
    def __init__(self, actions=None):
        if actions is not None:
            self._actions = actions
        else:
            self._actions = registry._actions if "registry" in globals() else {}

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



    
def _business_insights(parameters=None, user_id=None):
    """Read-only organization-scoped business intelligence action."""
    parameters = dict(parameters or {})

    organization_id = parameters.get("organization_id")
    if organization_id is None:
        return {
            "success": False,
            "status": "blocked",
            "type": "business_insights",
            "error": "organization_id_required",
            "message": "Organization context is required for business insights.",
        }

    try:
        organization_id = int(organization_id)
    except (TypeError, ValueError):
        return {
            "success": False,
            "status": "blocked",
            "type": "business_insights",
            "error": "invalid_organization_id",
            "message": "Invalid organization context.",
        }

    try:
        from app.core.context.live_business_data import LiveBusinessData
        from app.core.sales.sales_engine import SalesEngine
        from app.core.revenue.revenue_engine import RevenueEngine
        from app.core.analytics.roi_engine import ROIEngine
        from app.services.bos_intelligence import BOSIntelligenceService

        snapshot = LiveBusinessData().snapshot(organization_id)
        data = snapshot.to_dict()

        sales = SalesEngine.analyze(
            leads=data.get("leads", 0),
            qualified_leads=data.get("qualified_leads", 0),
            opportunities=data.get("opportunities", 0),
            customers=data.get("customers", 0),
            pipeline_value=data.get("pipeline_value", 0.0),
            average_deal_value=data.get("average_deal_value", 0.0),
        )

        revenue = RevenueEngine().analyze(
            leads=data.get("leads", 0),
            opportunities=data.get("opportunities", 0),
            customers=data.get("customers", 0),
            revenue=data.get("revenue", 0.0),
            pipeline_value=data.get("pipeline_value", 0.0),
        )

        roi = ROIEngine.calculate(
            revenue=data.get("revenue", 0.0),
            cost=0.0,
            customers=data.get("customers", 0),
            leads=data.get("leads", 0),
            automated_tasks=data.get("successful_executions", 0),
            manual_hours_saved=0.0,
        )

        executive_snapshot = BOSIntelligenceService.get_executive_snapshot(
            organization_id=organization_id,
        )

        return {
            "success": True,
            "status": "completed",
            "type": "business_insights",
            "message": "Business intelligence generated successfully.",
            "organization_id": organization_id,
            "user_id": user_id,
            "read_only": True,
            "external_execution": False,
            "database_mutation": False,
            "kpis": {
                "leads": data.get("leads", 0),
                "qualified_leads": data.get("qualified_leads", 0),
                "opportunities": data.get("opportunities", 0),
                "customers": data.get("customers", 0),
                "revenue": data.get("revenue", 0.0),
                "pipeline_value": data.get("pipeline_value", 0.0),
                "conversion_rate": data.get("conversion_rate", 0.0),
                "average_deal_value": data.get("average_deal_value", 0.0),
            },
            "sales": sales,
            "revenue": revenue,
            "roi": roi,
            "executive_snapshot": executive_snapshot,
        }

    except Exception as exc:
        return {
            "success": False,
            "status": "failed",
            "type": "business_insights",
            "error": "business_insights_failed",
            "message": str(exc),
            "organization_id": organization_id,
            "read_only": True,
            "external_execution": False,
            "database_mutation": False,
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


def _revenue_autopilot_plan(parameters, user_id=None):
    from app.services.revenue_autopilot_facade import RevenueAutopilotFacade

    parameters = parameters or {}
    lead_id = parameters.get("lead_id")
    organization_id = parameters.get("organization_id")

    if not lead_id:
        return {
            "success": False,
            "message": "lead_id is required",
        }

    if not organization_id:
        return {
            "success": False,
            "status": "blocked",
            "error": "organization_required",
        }

    return RevenueAutopilotFacade.plan_for_lead(
        int(lead_id),
        organization_id=int(organization_id),
    )


def _revenue_autopilot_run(parameters, user_id=None):
    from app.services.revenue_autopilot_facade import RevenueAutopilotFacade

    parameters = parameters or {}
    lead_id = parameters.get("lead_id")
    organization_id = parameters.get("organization_id")

    if not lead_id:
        return {
            "success": False,
            "message": "lead_id is required",
        }

    if not organization_id:
        return {
            "success": False,
            "status": "blocked",
            "error": "organization_required",
        }

    return RevenueAutopilotFacade.run_for_lead(
        int(lead_id),
        user_id=user_id,
        organization_id=int(organization_id),
    )


registry.register(
    "revenue_autopilot_plan",
    _revenue_autopilot_plan,
)

registry.register(
    "revenue_autopilot_run",
    _revenue_autopilot_run,
)

registry.register("business_insights", _business_insights)


# === GOVERNED ENGINEERING ACTIONS ===

def _engineering_health(parameters=None, user_id=None):
    return {
        "success": True,
        "status": "completed",
        "action": "health",
        "message": "Kemet AI health check passed.",
        "data": {"result": "KEMET_HEALTH_OK"},
        "read_only": True,
        "external_execution": False,
        "database_mutation": False,
    }


def _engineering_test_health(parameters=None, user_id=None):
    return {
        "success": True,
        "status": "completed",
        "action": "test_health",
        "message": "Kemet AI test health check passed.",
        "data": {"result": "KEMET_TEST_HEALTH_OK"},
        "read_only": True,
        "external_execution": False,
        "database_mutation": False,
    }


def _engineering_compile(parameters=None, user_id=None):
    import subprocess

    result = subprocess.run(
        ["python", "-m", "compileall", "-q", "app", "agent"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        timeout=120,
    )

    return {
        "success": result.returncode == 0,
        "status": "completed" if result.returncode == 0 else "failed",
        "action": "compile",
        "data": {
            "returncode": result.returncode,
            "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-12000:],
        },
        "external_execution": False,
        "database_mutation": False,
    }


def _engineering_git_status(parameters=None, user_id=None):
    import subprocess

    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        timeout=120,
    )

    return {
        "success": result.returncode == 0,
        "status": "completed" if result.returncode == 0 else "failed",
        "action": "git_status",
        "data": {
            "returncode": result.returncode,
            "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-12000:],
        },
        "read_only": True,
        "external_execution": False,
        "database_mutation": False,
    }


registry.register("health", _engineering_health)
registry.register("test_health", _engineering_test_health)
registry.register("compile", _engineering_compile)
registry.register("git_status", _engineering_git_status)
