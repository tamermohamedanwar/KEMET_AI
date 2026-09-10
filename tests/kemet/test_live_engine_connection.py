import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_live_business_engines_connection():
    from wsgi import application

    with application.app_context():
        from app.core.context.live_business_data import LiveBusinessData
        from app.core.intelligence.intelligence_service import IntelligenceService
        from app.core.revenue.revenue_engine import RevenueEngine
        from app.core.sales.sales_engine import SalesEngine
        from app.core.customer.customer_engine import CustomerEngine
        from app.core.analytics.roi_engine import ROIEngine

        snapshot = LiveBusinessData().snapshot(1)
        data = snapshot.to_dict()

        intelligence = IntelligenceService()

        revenue = RevenueEngine().analyze(
            leads=data["leads"],
            opportunities=data["opportunities"],
            customers=data["customers"],
            revenue=data["revenue"],
            pipeline_value=data["pipeline_value"],
        )

        sales = SalesEngine().analyze(
            leads=data["leads"],
            qualified_leads=data["qualified_leads"],
            opportunities=data["opportunities"],
            customers=data["customers"],
            pipeline_value=data["pipeline_value"],
        )

        customer = CustomerEngine().build_customer_context(
            customer_id=1,
            channel="web",
            message="Live Kemet business context test",
        )

        roi = ROIEngine().calculate(
            revenue=data["revenue"],
            cost=0,
            customers=data["customers"],
            leads=data["leads"],
            automated_tasks=data["successful_executions"],
            manual_hours_saved=0,
        )

        assert revenue["success"] is True
        assert sales["success"] is True
        assert customer["success"] is True
        assert roi["success"] is True

        assert revenue["metrics"]["revenue"] == data["revenue"]
        assert sales["metrics"]["leads"] == data["leads"]
        assert roi["metrics"]["revenue"] == data["revenue"]

        assert intelligence is not None


def test_live_business_context_is_read_only():
    from wsgi import application

    with application.app_context():
        from app.core.context.live_business_data import LiveBusinessData

        before = LiveBusinessData().snapshot(1).to_dict()
        after = LiveBusinessData().snapshot(1).to_dict()

        assert before == after


def test_global_and_org_context_are_distinct():
    from wsgi import application

    with application.app_context():
        from app.core.context.live_business_data import LiveBusinessData

        service = LiveBusinessData()

        global_data = service.snapshot().to_dict()
        org_data = service.snapshot(1).to_dict()

        assert global_data["organization_id"] is None
        assert org_data["organization_id"] == 1

        assert global_data["revenue"] >= org_data["revenue"]
        assert global_data["users"] >= org_data["users"]
