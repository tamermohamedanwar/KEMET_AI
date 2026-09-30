import json

from app import db
from app.models.automation import AutomationApproval
from app.models.demo_lead import DemoLead
from app.models.lead_activity import LeadActivity
from app.services.bos_runtime import bos_runtime
from app.services.commerce_revenue_workflow_service import commerce_revenue_workflow_service
from wsgi import application


def test_commerce_workflow_enters_approval_without_side_effect():
    result = commerce_revenue_workflow_service.build_plan(
        organization_id=1,
        product={"name": "Kemet Commerce Package", "price": 100},
        qualification={"status": "qualified", "missing_fields": [], "score": 95},
        lead_id=6,
        customer_id=6,
        channel="web",
    )
    assert result["status"] == "approval_required"
    assert result["commercial"]["revenue"] == "not_available"
    assert result["commercial"]["roi"] == "not_proven"
    assert result["commercial"]["causal_claim"] is False


def test_commerce_followup_approval_executes_canonical_sales_action():
    with application.app_context():
        _test_commerce_followup_approval_executes_canonical_sales_action()


def _test_commerce_followup_approval_executes_canonical_sales_action():
    lead_id = 6
    before = LeadActivity.query.filter_by(organization_id=1, lead_id=lead_id).count()
    result = bos_runtime.operate(
        f"follow up customer #{lead_id}", organization_id=1, user_id=1
    )
    assert result["status"] == "waiting_approval"
    assert result["executed"] is False
    approval_id = result["approval_id"]
    approval = db.session.get(AutomationApproval, approval_id)
    assert approval is not None
    assert approval.status == "pending"
    assert approval.action_type == "sales_follow_up"
    request_data = json.loads(approval.request_json or "{}")
    assert request_data.get("action") == "sales_follow_up"
    assert request_data.get("parameters", {}).get("lead_id") == lead_id
    assert LeadActivity.query.filter_by(organization_id=1, lead_id=lead_id).count() == before

    approved = bos_runtime.approve(approval_id, organization_id=1, user_id=1)
    assert approved["success"] is True
    assert approved["status"] == "approved"
    assert approved["execution"]["success"] is True
    assert LeadActivity.query.filter_by(organization_id=1, lead_id=lead_id).count() == before + 1
    assert db.session.get(DemoLead, lead_id).organization_id == 1
