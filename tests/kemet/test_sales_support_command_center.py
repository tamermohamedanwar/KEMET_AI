from datetime import datetime, timedelta

from app import db
from app.models.demo_lead import DemoLead
from app import create_app
from app.services.sales_support_command_center import sales_support_command_center
from wsgi import application


def test_sales_support_snapshot_is_tenant_scoped():
    with application.app_context():
        now = datetime.utcnow()
        db.session.add_all([
            DemoLead(organization_id=999001, company_name="Hot Co", email="hot@example.com", status="qualified", lead_score=90, estimated_value=10000, phone="01000000000", source="website", message="High intent buyer requesting a business demo", next_follow_up_at=now - timedelta(hours=1)),
            DemoLead(organization_id=999001, company_name="Warm Co", email="warm@example.com", status="new", lead_score=60, estimated_value=5000, next_follow_up_at=now + timedelta(days=1)),
            DemoLead(organization_id=999002, company_name="Other Co", email="other@example.com", status="new", lead_score=100, estimated_value=99999, next_follow_up_at=now - timedelta(hours=1)),
        ])
        db.session.commit()

        result = sales_support_command_center.snapshot(organization_id=999001)

        assert result["total_leads"] == 2
        assert result["hot_leads"] == 1
        assert result["follow_ups_due"] == 1
        assert result["pipeline_value"] == 15000.0
        assert result["recommended_action"] == "follow_up_now"
        assert result["top_leads"][0]["company_name"] == "Hot Co"
        assert result["top_leads"][0]["recommended_action"] == "follow_up_now"
        assert result["governance"]["read_only"] is True
        assert result["governance"]["external_execution"] is False


def test_sales_support_rejects_invalid_organization():
    try:
        sales_support_command_center.snapshot(organization_id=0)
    except ValueError as exc:
        assert str(exc) == "organization_required"
    else:
        raise AssertionError("invalid organization must be rejected")


def test_sales_support_snapshot_is_advisory_only():
    app = create_app()
    with app.app_context():
        result = sales_support_command_center.snapshot(organization_id=1)
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["approval_required"] is True
