from datetime import datetime, timedelta

from app import db
from app.models.demo_lead import DemoLead
from app.models.ticket import Ticket
from app.models.user import User
from app.services.distribution_service import distribution_service
from wsgi import application


def _user(org, email, name, role="user"):
    return User(organization_id=org, full_name=name, email=email, password_hash="x", role=role)


def test_distribution_is_tenant_scoped_and_advisory():
    with application.app_context():
        org = 998801
        other = 998802
        alice = _user(org, "dist-alice@example.com", "Alice")
        bob = _user(org, "dist-bob@example.com", "Bob")
        outsider = _user(other, "dist-outsider@example.com", "Outsider")
        db.session.add_all([alice, bob, outsider])
        db.session.flush()
        db.session.add_all([
            DemoLead(organization_id=org, company_name="Priority Co", email="priority@example.com", status="qualified", lead_score=90, estimated_value=10000, next_follow_up_at=datetime.utcnow() - timedelta(hours=1)),
            DemoLead(organization_id=org, company_name="Assigned Co", email="assigned@example.com", status="new", lead_score=60, estimated_value=3000, owner_id=alice.id),
            DemoLead(organization_id=other, company_name="Other Co", email="other-dist@example.com", status="qualified", lead_score=100, estimated_value=99999),
        ])
        db.session.add(Ticket(organization_id=org, title="Open ticket", status="open", priority="high", assigned_to_id=alice.id))
        db.session.commit()

        result = distribution_service.preview_sales(organization_id=org)

        assert result["candidate_count"] == 2
        assert len(result["recommendations"]) == 2
        assert all(row["organization_id"] == org for row in result["recommendations"])
        assert all(row["owner_id"] in {alice.id, bob.id} for row in result["recommendations"])
        assert result["recommendations"][0]["owner_id"] == bob.id
        assert result["recommendations"][1]["reason"] == "retain_existing_owner"
        assert result["governance"]["read_only"] is True
        assert result["governance"]["database_mutation"] is False


def test_distribution_rejects_invalid_organization():
    try:
        distribution_service.preview_sales(organization_id=0)
    except ValueError as exc:
        assert str(exc) == "organization_required"
    else:
        raise AssertionError("invalid organization must be rejected")
