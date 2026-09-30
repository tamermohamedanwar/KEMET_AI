from app import create_app, db
from app.models.lead_intelligence_evidence import LeadIntelligenceEvidence
from app.services.lead_discovery_service import lead_discovery_service


def test_allowed_source_ingestion_is_tenant_bound_and_evidenced():
    app = create_app()
    with app.app_context():
        result = lead_discovery_service.ingest_one(
            tenant_id=1,
            source="google_sheets",
            record={
                "company_name": "Discovery Co",
                "email": "discovery@example.com",
                "phone": "+20 100 555 1212",
                "message": "Interested in governed sales automation.",
                "estimated_value": 900,
                "provenance": {"source": "google_sheets", "sheet": "Leads"},
            },
        )
        assert result["status"] == "created"
        assert len(result["evidence_digest"]) == 64
        assert LeadIntelligenceEvidence.query.filter_by(lead_id=result["lead_id"]).count() == 1
        db.session.rollback()


def test_duplicate_ingestion_is_suppressed_deterministically():
    app = create_app()
    with app.app_context():
        record = {"company_name": "Dup Co", "email": "dup@example.com", "phone": "01001234567"}
        first = lead_discovery_service.ingest_one(tenant_id=1, source="crm", record=record)
        second = lead_discovery_service.ingest_one(tenant_id=1, source="crm", record=record)
        assert first["status"] == "created"
        assert second["status"] == "duplicate"
        assert second["lead_id"] == first["lead_id"]
        db.session.rollback()


def test_disallowed_source_fails_closed():
    app = create_app()
    with app.app_context():
        try:
            lead_discovery_service.ingest_one(tenant_id=1, source="unknown_scraper", record={"email": "x@example.com"})
        except ValueError as exc:
            assert str(exc) == "lead_source_not_allowed"
        else:
            raise AssertionError("unapproved source must be rejected")
