from types import SimpleNamespace

import pytest

from app.services.business_intelligence_pipeline_service import business_intelligence_pipeline
from app.services.provider_decision_intelligence_service import provider_decision_intelligence


def make_bi():
    lead = SimpleNamespace(
        id=901, organization_id=7, tenant_id=7, company_name="Acme",
        email="sales@example.com", phone="+201001234567",
        message="Need proposal", source="crm", status="new",
        estimated_value=2000, provenance={"source": "crm"},
        lead_score=80, created_at=None, updated_at=None,
    )
    return business_intelligence_pipeline.build(lead, persist_evidence=False)


def test_provider_review_redacts_direct_lead_fields(monkeypatch):
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return SimpleNamespace(content="advisory", provider_id="openai", model="gpt-5.6", input_tokens=10, output_tokens=5, total_tokens=15)

    monkeypatch.setattr("app.services.provider_decision_intelligence_service.federated_generate", fake_generate)
    result = provider_decision_intelligence.analyze(make_bi(), organization_id=7)
    assert result["provider"] == "openai"
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["human_approval_required"] is True
    assert "sales@example.com" not in captured["prompt"]
    assert "+201001234567" not in captured["prompt"]
    assert len(result["input_digest"]) == 64
    assert len(result["output_digest"]) == 64


def test_provider_review_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr("app.services.provider_decision_intelligence_service.federated_generate", lambda *a, **k: None)
    bi = make_bi()
    with pytest.raises(ValueError, match="tenant_mismatch"):
        provider_decision_intelligence.analyze(bi, organization_id=8)


def test_provider_review_requires_tenant(monkeypatch):
    monkeypatch.setattr("app.services.provider_decision_intelligence_service.federated_generate", lambda *a, **k: None)
    with pytest.raises(ValueError, match="tenant_id_required"):
        provider_decision_intelligence.analyze({"decision": {}}, organization_id=7)


def test_provider_review_binds_observed_request_cost_and_provenance(monkeypatch):
    def fake_generate(prompt, **kwargs):
        return SimpleNamespace(
            content="advisory", provider_id="openai", model="gpt-5.6",
            input_tokens=10, output_tokens=5, total_tokens=15,
            request_id="req-77", metadata={"cost_usd": 0.0025},
        )

    monkeypatch.setattr("app.services.provider_decision_intelligence_service.federated_generate", fake_generate)
    result = provider_decision_intelligence.analyze(make_bi(), organization_id=7)
    assert result["cost"] == 0.0025
    assert result["cost_status"] == "observed"
    assert result["provenance_lineage"]["schema"] == "kemet.provenance_lineage.v1"
    assert result["provenance_lineage"]["nodes"][0]["metadata"]["request_id"] == "req-77"
    assert result["decision_record"]["schema"] == "kemet.provider_decision_record.v1"
    assert result["decision_record"]["status"] == "review_required"
    assert result["decision_record"]["provenance_digest"] == result["provenance_lineage"]["digest"]
    assert result["decision_record"]["evidence_digest"] == result["evidence_digest"]
    assert len(result["decision_record"]["digest"]) == 64
    assert result["control_evidence_chain"]["stages"][0]["status"] == "review_required"
    assert result["control_evidence_chain"]["stages"][2]["status"] == "not_executed"
    assert result["governance"]["external_execution"] is False
