import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_live_business_data_read_only():
    from wsgi import application
    from app.core.context.live_business_data import LiveBusinessData

    with application.app_context():
        service = LiveBusinessData()
        snapshot = service.snapshot()

        assert snapshot.leads >= 0
        assert snapshot.revenue >= 0
        assert snapshot.customers >= 0
        assert snapshot.total_tickets >= 0
        assert snapshot.automation_executions >= 0

        metrics = snapshot.to_dict()

        assert "leads" in metrics
        assert "qualified_leads" in metrics
        assert "converted_leads" in metrics
        assert "pipeline_value" in metrics
        assert "revenue" in metrics
        assert "customers" in metrics
        assert "open_tickets" in metrics
        assert "automation_executions" in metrics
        assert "ai_requests" in metrics
        assert "active_subscriptions" in metrics


def test_organization_scoped_snapshot():
    from wsgi import application
    from app.core.context.live_business_data import LiveBusinessData

    with application.app_context():
        service = LiveBusinessData()

        first = service.snapshot(1)
        second = service.snapshot(2)

        assert first.organization_id == 1
        assert second.organization_id == 2

        assert first.to_dict()["organization_id"] == 1
        assert second.to_dict()["organization_id"] == 2


def test_business_calculations():
    from app.core.context.live_business_data import BusinessSnapshot

    snapshot = BusinessSnapshot(
        organization_id=1,
        organization_name="Test",
        leads=10,
        qualified_leads=5,
        converted_leads=2,
        lost_leads=1,
        pipeline_value=1000,
        revenue=400,
        customers=2,
        users=3,
        open_tickets=1,
        total_tickets=2,
        ticket_replies=4,
        conversations=5,
        chat_messages=8,
        active_workflows=2,
        automation_executions=10,
        successful_executions=8,
        ai_requests=20,
        ai_tokens=1000,
        active_subscriptions=1,
        paid_payments=2,
        pending_payments=1,
        lead_activities=3,
    )

    assert snapshot.opportunity_count == 5
    assert snapshot.average_deal_value == 200.0
    assert snapshot.lead_to_customer_rate == 20.0
    assert snapshot.qualification_rate == 50.0
