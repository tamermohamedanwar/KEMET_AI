import pytest

from app import create_app, db
from app.models.organization import Organization
from app.models.payment import Payment
from app.services.revenue_pipeline_service import revenue_pipeline_service


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True)
    with application.app_context():
        organization = Organization(name="Revenue Pipeline Test", slug="revenue-pipeline-test")
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


def test_revenue_pipeline_full_lifecycle(app, organization):
    with app.app_context():
        created = revenue_pipeline_service.intake(
            organization_id=organization.id, company_name="Pipeline Customer", email="pipeline@example.com",
            offer_name="Content Package", quoted_amount="5000",
        )
        key = created["pipeline_key"]
        assert created["stage"] == "inquiry"
        revenue_pipeline_service.advance(organization_id=organization.id, pipeline_key=key, stage="qualified")
        revenue_pipeline_service.advance(organization_id=organization.id, pipeline_key=key, stage="proposal")
        revenue_pipeline_service.advance(organization_id=organization.id, pipeline_key=key, stage="awaiting_payment")
        payment = Payment(organization_id=organization.id, plan="business", amount=5000, currency="EGP", status="paid", provider="paymob", provider_transaction_id="txn-pipeline-001")
        db.session.add(payment)
        db.session.commit()
        paid = revenue_pipeline_service.attach_payment(organization_id=organization.id, pipeline_key=key, payment_id=payment.id)
        assert paid["paid_amount"] == 5000.0
        revenue_pipeline_service.record_cost(organization_id=organization.id, pipeline_key=key, category="fulfillment", amount="1200")
        revenue_pipeline_service.record_cost(organization_id=organization.id, pipeline_key=key, category="provider_fee", amount="150")
        delivered = revenue_pipeline_service.attach_delivery(organization_id=organization.id, pipeline_key=key, fulfillment_reference="delivery-001")
        assert delivered["stage"] == "delivered"
        closed = revenue_pipeline_service.close(organization_id=organization.id, pipeline_key=key)
        assert closed["stage"] == "closed"
        assert closed["profit"] == 3650.0
        assert closed["margin_pct"] == 73.0


def test_profit_is_not_verified_before_a_bound_paid_payment(app, organization):
    with app.app_context():
        created = revenue_pipeline_service.intake(
            organization_id=organization.id, company_name="Cost Only", email="cost-only@example.com", quoted_amount=1000
        )
        revenue_pipeline_service.record_cost(organization_id=organization.id, pipeline_key=created["pipeline_key"], category="acquisition", amount=100)
        snapshot = revenue_pipeline_service.snapshot(
            db.session.get(__import__("app.models.revenue_pipeline", fromlist=["RevenuePipelineRecord"]).RevenuePipelineRecord, created["id"])
        )
        assert snapshot["profit"] == 0.0
        assert snapshot["margin_pct"] == 0.0
        assert snapshot["profit_status"] == "not_verified"
        assert snapshot["financial_evidence"]["claimed_profit_accepted"] is False


def test_payment_is_server_derived_and_tenant_bound(app, organization):
    with app.app_context():
        created = revenue_pipeline_service.intake(
            organization_id=organization.id, company_name="A", email="a@example.com", quoted_amount=1000
        )
        payment = Payment(organization_id=organization.id, plan="starter", amount=1000, currency="EGP", status="pending", provider="paymob")
        db.session.add(payment)
        db.session.commit()
        with pytest.raises(ValueError, match="payment_not_completed"):
            revenue_pipeline_service.attach_payment(organization_id=organization.id, pipeline_key=created["pipeline_key"], payment_id=payment.id)


def test_paid_stage_requires_verified_payment(app, organization):
    with app.app_context():
        created = revenue_pipeline_service.intake(
            organization_id=organization.id, company_name="C", email="c@example.com", quoted_amount=1000
        )
        for stage in ("qualified", "proposal", "awaiting_payment"):
            revenue_pipeline_service.advance(
                organization_id=organization.id, pipeline_key=created["pipeline_key"], stage=stage
            )
        with pytest.raises(ValueError, match="paid_stage_requires_verified_payment"):
            revenue_pipeline_service.advance(
                organization_id=organization.id, pipeline_key=created["pipeline_key"], stage="paid"
            )


def test_payment_binding_requires_awaiting_payment_stage(app, organization):
    with app.app_context():
        created = revenue_pipeline_service.intake(
            organization_id=organization.id, company_name="D", email="d@example.com", quoted_amount=1000
        )
        payment = Payment(
            organization_id=organization.id, plan="starter", amount=1000, currency="EGP",
            status="paid", provider="paymob", provider_transaction_id="txn-stage-bound-001"
        )
        db.session.add(payment)
        db.session.commit()
        with pytest.raises(ValueError, match="payment_requires_awaiting_payment"):
            revenue_pipeline_service.attach_payment(
                organization_id=organization.id, pipeline_key=created["pipeline_key"], payment_id=payment.id
            )


def test_payment_binding_rejects_amount_currency_and_reuse(app, organization):
    with app.app_context():
        created = revenue_pipeline_service.intake(
            organization_id=organization.id, company_name="E", email="e@example.com",
            quoted_amount=1000,
        )
        for stage in ("qualified", "proposal", "awaiting_payment"):
            revenue_pipeline_service.advance(
                organization_id=organization.id, pipeline_key=created["pipeline_key"], stage=stage
            )
        wrong_amount = Payment(
            organization_id=organization.id, plan="starter", amount=900, currency="EGP",
            status="paid", provider="paymob", provider_transaction_id="txn-wrong-amount"
        )
        db.session.add(wrong_amount)
        db.session.commit()
        with pytest.raises(ValueError, match="payment_amount_mismatch"):
            revenue_pipeline_service.attach_payment(
                organization_id=organization.id, pipeline_key=created["pipeline_key"], payment_id=wrong_amount.id
            )
        wrong_currency = Payment(
            organization_id=organization.id, plan="starter", amount=1000, currency="USD",
            status="paid", provider="paymob", provider_transaction_id="txn-wrong-currency"
        )
        db.session.add(wrong_currency)
        db.session.commit()
        with pytest.raises(ValueError, match="payment_currency_mismatch"):
            revenue_pipeline_service.attach_payment(
                organization_id=organization.id, pipeline_key=created["pipeline_key"], payment_id=wrong_currency.id
            )
        valid = Payment(
            organization_id=organization.id, plan="starter", amount=1000, currency="EGP",
            status="paid", provider="paymob", provider_transaction_id="txn-valid-reuse"
        )
        db.session.add(valid)
        db.session.commit()
        revenue_pipeline_service.attach_payment(
            organization_id=organization.id, pipeline_key=created["pipeline_key"], payment_id=valid.id
        )
        with pytest.raises(ValueError, match="payment_already_bound"):
            revenue_pipeline_service.attach_payment(
                organization_id=organization.id, pipeline_key=created["pipeline_key"], payment_id=valid.id
            )


def test_invalid_stage_transition_fails_closed(app, organization):
    with app.app_context():
        created = revenue_pipeline_service.intake(
            organization_id=organization.id, company_name="B", email="b@example.com", quoted_amount=1000
        )
        with pytest.raises(ValueError, match="invalid_revenue_stage_transition"):
            revenue_pipeline_service.advance(organization_id=organization.id, pipeline_key=created["pipeline_key"], stage="delivered")
