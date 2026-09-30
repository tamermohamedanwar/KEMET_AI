from types import SimpleNamespace

from app.services.lead_intelligence_service import lead_intelligence_service
from app.services.lead_scoring_service import score_lead


def make_lead(**overrides):
    values = {
        "id": 101,
        "organization_id": 7,
        "tenant_id": 7,
        "company_name": "  Acme   Egypt  ",
        "email": " SALES@ACME.EG ",
        "phone": "+20 (100) 123-4567",
        "message": "We need a proposal for a business automation platform.",
        "source": "Website",
        "status": "new",
        "estimated_value": 1500,
        "created_at": None,
        "updated_at": None,
        "lead_score": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_canonical_lead_schema_is_normalized_and_tenant_bound():
    result = lead_intelligence_service.canonicalize(make_lead())
    assert result["schema"] == "kemet.canonical_lead.v1"
    assert result["tenant_id"] == 7
    assert result["identity"]["company"] == "acme egypt"
    assert result["identity"]["email"] == "sales@acme.eg"
    assert result["identity"]["phone"] == "201001234567"
    assert len(result["dedup_key"]) == 64


def test_dedup_key_changes_across_tenants():
    first = lead_intelligence_service.deduplication_key(make_lead(tenant_id=7)) if hasattr(lead_intelligence_service, "deduplication_key") else lead_intelligence_service.deduplicate_key(make_lead(tenant_id=7))
    second = lead_intelligence_service.deduplicate_key(make_lead(tenant_id=8, organization_id=8))
    assert first != second


def test_qualification_is_explainable():
    result = lead_intelligence_service.qualification(lead_intelligence_service.canonicalize(make_lead()))
    assert result["method"] == "evidence_rule_v1"
    assert result["status"] == "qualified"
    assert result["confidence"] >= 0.60
    assert all(isinstance(value, bool) for value in result["checks"].values())


def test_scoring_is_evidence_weighted_not_status_weighted():
    lead = make_lead(status="won", estimated_value=0, message="")
    result = score_lead(lead)
    assert result["method"] == "evidence_weighted_v1"
    assert 0 <= result["score"] <= 100
    assert "qualification_confidence" in result["evidence"]
    assert len(result["evidence_digest"]) == 64


def test_unbound_lead_fails_closed():
    try:
        lead_intelligence_service.canonicalize(make_lead(tenant_id=None, organization_id=None))
    except ValueError as exc:
        assert str(exc) == "tenant_id_required"
    else:
        raise AssertionError("unbound lead must fail closed")


def test_provenance_is_preserved_in_canonical_schema():
    lead = make_lead(provenance={"source": "google_sheets", "record": "row-9"})
    result = lead_intelligence_service.canonicalize(lead)
    assert result["provenance"]["source"] == "google_sheets"
