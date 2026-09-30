import pytest

from app import create_app, db
from app.models.organization import Organization
from app.models.payment import Payment
from app.services.revenue_first_commercial_cycle_service import (
    revenue_first_commercial_cycle_service,
)
from app.services.revenue_pipeline_service import revenue_pipeline_service


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True)
    with application.app_context():
        organization = Organization(
            name="Revenue First Cycle Test",
            slug="revenue-first-cycle-test",
        )
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


def _prepared(organization):
    return revenue_first_commercial_cycle_service.prepare(
        organization_id=organization.id,
        content={
            "content_id": "mendes-ep-001",
            "verified": True,
            "artifact_digest": "artifact-digest-001",
        },
        distribution={
            "verified": True,
            "channel": "telegram",
            "publication_id": "manual-approved-pub-001",
            "cta": "Continue the story on Telegram.",
        },
        offer={
            "name": "Sponsored Cinematic Short",
            "quoted_amount": 5000,
            "currency": "EGP",
        },
    )


def test_prepare_binds_the_full_profit_cycle_without_external_execution(app, organization):
    with app.app_context():
        result = _prepared(organization)
        assert result["status"] == "ready_for_lead"
        assert result["stages"] == [
            "verified_content",
            "verified_distribution",
            "cta_lead",
            "offer",
            "payment",
            "fulfillment",
            "profit",
            "learning",
        ]
        assert result["distribution"]["external_publication_executed"] is False
        assert result["governance"]["auto_payment"] is False
        assert result["governance"]["human_approval_required"] is True


def test_real_cycle_reaches_verified_payment_fulfillment_and_profit(app, organization):
    with app.app_context():
        prepared = _prepared(organization)
        lead = revenue_first_commercial_cycle_service.intake_lead(
            prepared=prepared,
            company_name="First Buyer",
            email="buyer@example.com",
            message="I want the sponsored short.",
        )
        key = lead["pipeline_key"]
        revenue_pipeline_service.advance(
            organization_id=organization.id, pipeline_key=key, stage="qualified"
        )
        revenue_pipeline_service.advance(
            organization_id=organization.id, pipeline_key=key, stage="proposal"
        )
        revenue_pipeline_service.advance(
            organization_id=organization.id, pipeline_key=key, stage="awaiting_payment"
        )
        payment = Payment(
            organization_id=organization.id,
            plan="business",
            amount=5000,
            currency="EGP",
            status="paid",
            provider="paymob",
            provider_transaction_id="cycle-payment-001",
        )
        db.session.add(payment)
        db.session.commit()
        paid = revenue_pipeline_service.attach_payment(
            organization_id=organization.id,
            pipeline_key=key,
            payment_id=payment.id,
        )
        assert paid["stage"] == "paid"
        revenue_pipeline_service.record_cost(
            organization_id=organization.id,
            pipeline_key=key,
            category="fulfillment",
            amount=1250,
        )
        delivered = revenue_pipeline_service.attach_delivery(
            organization_id=organization.id,
            pipeline_key=key,
            fulfillment_reference="delivery-001",
        )
        assert delivered["stage"] == "delivered"
        closed = revenue_pipeline_service.close(
            organization_id=organization.id, pipeline_key=key
        )
        assert closed["stage"] == "closed"
        assert closed["profit"] == 3750.0
        assert closed["margin_pct"] == 75.0


def test_cycle_control_surface_delegates_payment_fulfillment_cost_and_close(app, organization):
    with app.app_context():
        prepared = _prepared(organization)
        lead = revenue_first_commercial_cycle_service.intake_lead(
            prepared=prepared, company_name="Control Buyer", email="control@example.com"
        )
        key = lead["pipeline_key"]
        for stage in ("qualified", "proposal", "awaiting_payment"):
            revenue_first_commercial_cycle_service.advance(
                organization_id=organization.id, pipeline_key=key, stage=stage
            )
        payment = Payment(
            organization_id=organization.id, plan="business", amount=5000,
            currency="EGP", status="paid", provider="paymob",
            provider_transaction_id="cycle-control-payment-001",
        )
        db.session.add(payment)
        db.session.commit()
        paid = revenue_first_commercial_cycle_service.record_payment(
            organization_id=organization.id, pipeline_key=key, payment_id=payment.id
        )
        assert paid["stage"] == "paid"
        revenue_first_commercial_cycle_service.record_cost(
            organization_id=organization.id, pipeline_key=key, category="fulfillment", amount=900
        )
        delivered = revenue_first_commercial_cycle_service.fulfill(
            organization_id=organization.id, pipeline_key=key, fulfillment_reference="cycle-control-delivery"
        )
        assert delivered["stage"] == "delivered"
        closed = revenue_first_commercial_cycle_service.close(
            organization_id=organization.id, pipeline_key=key
        )
        assert closed["stage"] == "closed"
        assert closed["profit"] == 4100.0


def test_learning_requires_observed_evidence_and_stays_advisory(app, organization):
    with app.app_context():
        result = revenue_first_commercial_cycle_service.learning(
            organization_id=organization.id,
            episode={"episode_id": "mendes-ep-001", "title": "الخاتم الأزرق"},
            observed={
                "metrics": {
                    "views": 10000,
                    "qualified_views": 4000,
                    "retention_rate": 58,
                    "shares": 700,
                    "revenue": 3750,
                }
            },
        )
        assert result["status"] == "recommendation"
        assert result["signals"]["revenue"] == "strong"
        assert result["human_approval_required"] is True
        assert result["execution_authority"] is False


def test_verified_cycle_requires_artifact_and_publication_evidence(app, organization):
    with app.app_context():
        with pytest.raises(ValueError, match="artifact_digest_required"):
            revenue_first_commercial_cycle_service.prepare(
                organization_id=organization.id,
                content={"content_id": "c1", "verified": True},
                distribution={"verified": True, "channel": "telegram", "publication_id": "pub-1", "cta": "join"},
                offer={"name": "Offer", "quoted_amount": 100},
            )
        with pytest.raises(ValueError, match="distribution_publication_id_required"):
            revenue_first_commercial_cycle_service.prepare(
                organization_id=organization.id,
                content={"content_id": "c1", "verified": True, "artifact_digest": "digest-1"},
                distribution={"verified": True, "channel": "telegram", "cta": "join"},
                offer={"name": "Offer", "quoted_amount": 100},
            )


def test_cycle_digest_binds_content_and_publication_identity(app, organization):
    with app.app_context():
        first = _prepared(organization)
        changed_content = revenue_first_commercial_cycle_service.prepare(
            organization_id=organization.id,
            content={
                "content_id": "mendes-ep-001",
                "verified": True,
                "artifact_digest": "artifact-digest-CHANGED",
            },
            distribution={
                "verified": True,
                "channel": "telegram",
                "publication_id": "manual-approved-pub-001",
                "cta": "Continue the story on Telegram.",
            },
            offer={"name": "Sponsored Cinematic Short", "quoted_amount": 5000, "currency": "EGP"},
        )
        changed_publication = revenue_first_commercial_cycle_service.prepare(
            organization_id=organization.id,
            content={
                "content_id": "mendes-ep-001",
                "verified": True,
                "artifact_digest": "artifact-digest-001",
            },
            distribution={
                "verified": True,
                "channel": "telegram",
                "publication_id": "manual-approved-pub-CHANGED",
                "cta": "Continue the story on Telegram.",
            },
            offer={"name": "Sponsored Cinematic Short", "quoted_amount": 5000, "currency": "EGP"},
        )
        assert first["identity"]["cycle_digest"] != changed_content["identity"]["cycle_digest"]
        assert first["identity"]["cycle_digest"] != changed_publication["identity"]["cycle_digest"]


def test_offer_terms_fail_closed(app, organization):
    with app.app_context():
        base = {
            "content": {"content_id": "c1", "verified": True, "artifact_digest": "digest-1"},
            "distribution": {"verified": True, "channel": "telegram", "publication_id": "pub-1", "cta": "join"},
        }
        with pytest.raises(ValueError, match="offer_amount_must_be_positive"):
            revenue_first_commercial_cycle_service.prepare(
                organization_id=organization.id,
                **base,
                offer={"name": "Offer", "quoted_amount": 0, "currency": "EGP"},
            )
        with pytest.raises(ValueError, match="invalid_offer_currency"):
            revenue_first_commercial_cycle_service.prepare(
                organization_id=organization.id,
                **base,
                offer={"name": "Offer", "quoted_amount": 100, "currency": "EG"},
            )

def test_unverified_content_or_distribution_fails_closed(app, organization):
    with app.app_context():
        with pytest.raises(ValueError, match="verified_content_required"):
            revenue_first_commercial_cycle_service.prepare(
                organization_id=organization.id,
                content={"content_id": "c1", "verified": False},
                distribution={
                    "verified": True,
                    "channel": "telegram",
                    "cta": "join",
                },
                offer={"name": "Offer", "quoted_amount": 100},
            )
        with pytest.raises(ValueError, match="verified_distribution_required"):
            revenue_first_commercial_cycle_service.prepare(
                organization_id=organization.id,
                content={"content_id": "c1", "verified": True},
                distribution={
                    "verified": False,
                    "channel": "telegram",
                    "cta": "join",
                },
                offer={"name": "Offer", "quoted_amount": 100},
            )
