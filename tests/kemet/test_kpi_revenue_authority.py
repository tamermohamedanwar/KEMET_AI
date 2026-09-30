import pytest

from app import create_app, db
from app.models.organization import Organization
from app.services.kpi_service import KPIService


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True)
    with application.app_context():
        organization = Organization(name="KPI Revenue Authority Test", slug="kpi-revenue-authority-test")
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


def test_kpi_revenue_is_pipeline_bound(app, organization):
    with app.app_context():
        result = KPIService.get_kpis(organization_id=organization.id, period="30d")
    revenue = result["revenue"]
    assert revenue["revenue_authority"] == "revenue_pipeline_verified_payment_binding"
    assert revenue["paid_amount"] >= 0
    assert "paid_amount_observational" in revenue


def test_kpi_requires_tenant_for_verified_commercial_revenue(app):
    with app.app_context():
        result = KPIService.get_kpis(organization_id=None, period="30d")
    revenue = result["revenue"]
    assert revenue["paid_amount"] == 0.0
    assert revenue["revenue_authority"] == "tenant_required_for_verified_commercial_revenue"
