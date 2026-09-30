import pytest

from app import create_app, db
from app.models.organization import Organization
from app.models.payment import Payment
from app.services.content_commerce_engine_service import content_commerce_engine_service


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True)
    with application.app_context():
        organization = Organization(name="Content Commerce Test", slug="content-commerce-test")
        db.session.add(organization)
        db.session.commit()
        application.test_organization_id = organization.id
    yield application
    with application.app_context():
        db.drop_all()


@pytest.fixture
def organization(app):
    with app.app_context():
        return db.session.get(Organization, app.test_organization_id)


def test_build_plan_exposes_profit_first_funnel(app, monkeypatch, organization):
    with app.app_context():
        monkeypatch.setattr(
            "app.services.content_commerce_engine_service.content_factory_service.build",
            lambda **kwargs: {"status": "review_required", "content_id": "artifact-1"},
        )
        result = content_commerce_engine_service.build_plan(
            organization_id=organization.id,
            title="Pilot",
            premise="A commercial story",
            content_id="artifact-1",
            offer_name="Sponsored Episode",
            quoted_amount=7500,
        )
        assert result["funnel"] == [
            "content_factory", "distribution", "audience_leads", "offers",
            "revenue_pipeline", "fulfillment", "profit_intelligence",
        ]
        assert result["offer"]["quoted_amount"] == 7500.0
        assert result["governance"]["human_approval_required"] is True


def test_intake_and_profit_intelligence_are_content_scoped(app, organization):
    with app.app_context():
        created = content_commerce_engine_service.intake_lead(
            organization_id=organization.id,
            content_id="mendes-ep-001",
            offer_name="Custom Cinematic Ad",
            company_name="Buyer One",
            email="buyer@example.com",
            quoted_amount=5000,
        )
        key = created["pipeline_key"]
        assert created["source"].startswith("content:mendes-ep-001:")
        from app.services.revenue_pipeline_service import revenue_pipeline_service
        revenue_pipeline_service.advance(organization_id=organization.id, pipeline_key=key, stage="qualified")
        revenue_pipeline_service.advance(organization_id=organization.id, pipeline_key=key, stage="proposal")
        revenue_pipeline_service.advance(organization_id=organization.id, pipeline_key=key, stage="awaiting_payment")
        payment = Payment(
            organization_id=organization.id, plan="business", amount=5000,
            currency="EGP", status="paid", provider="paymob",
            provider_transaction_id="txn-content-001",
        )
        db.session.add(payment)
        db.session.commit()
        revenue_pipeline_service.attach_payment(
            organization_id=organization.id, pipeline_key=key, payment_id=payment.id,
        )
        revenue_pipeline_service.record_cost(
            organization_id=organization.id, pipeline_key=key, category="fulfillment", amount=1000,
        )
        intelligence = content_commerce_engine_service.profit_intelligence(organization_id=organization.id)
        bucket = intelligence["by_content"]["mendes-ep-001"]
        assert bucket["paid_revenue"] == 5000.0
        assert bucket["cost"] == 1000.0
        assert bucket["profit"] == 4000.0
        assert bucket["margin_pct"] == 80.0
