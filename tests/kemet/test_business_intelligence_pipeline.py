from types import SimpleNamespace

import pytest

from app.services.business_intelligence_pipeline_service import business_intelligence_pipeline


def make_lead(**overrides):
    values = {
        "id": 501, "organization_id": 7, "tenant_id": 7,
        "company_name": "Acme Egypt", "email": "sales@acme.eg",
        "phone": "+20 100 123 4567",
        "message": "We need a proposal for governed business automation.",
        "source": "google_sheets", "status": "new", "estimated_value": 1500,
        "created_at": None, "updated_at": None, "lead_score": 80,
        "provenance": {"source": "google_sheets", "row": 2},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_pipeline_is_canonical_and_explainable():
    result = business_intelligence_pipeline.build(make_lead(), persist_evidence=False)
    assert result["schema"] == "kemet.business_intelligence.v1"
    assert result["tenant_id"] == 7
    assert result["enrichment"]["fields"]["email"]["confidence"] == 1.0
    assert "quality_dimensions" in result["data_quality"]
    assert result["segment"]["segment"] in {"high_intent", "qualified", "needs_enrichment", "low_signal"}
    assert result["decision"]["advisory"] is True
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["human_approval_required"] is True
    assert len(result["evidence_digest"]) == 64


def test_missing_data_routes_to_enrichment_first():
    result = business_intelligence_pipeline.build(
        make_lead(phone=None, message=None, estimated_value=0),
        persist_evidence=False,
    )
    assert result["missing_data"]
    assert result["decision"]["decision"] == "enrich_first"
    assert result["decision"]["recommended_next_step"] == "enrich_lead"


def test_cross_tenant_lookup_fails_closed():
    from app import create_app
    from app.models.demo_lead import DemoLead
    app = create_app()
    with app.app_context():
        with pytest.raises(ValueError, match="lead_not_found"):
            business_intelligence_pipeline.build_for_lead_id(999999, 999999, persist_evidence=False)
        assert DemoLead.query.filter_by(tenant_id=999999).count() == 0
