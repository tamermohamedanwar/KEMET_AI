from app.services.revenue_workforce_contract import revenue_workforce_contract


def test_revenue_workforce_contract_v1_is_provider_neutral_and_governed():
    result = revenue_workforce_contract.build(
        organization_id=1,
        product={"name": "Kemet Demo Product"},
        qualification={"status": "qualified", "missing_fields": [], "score": 95},
        lead_id=6,
        channel="web",
    )
    assert result["success"] is True
    assert result["contract"] == "Kemet Revenue Workforce"
    assert result["version"] == "1.0"
    assert result["authority"]["specialists"] == "propose_reason_research_prepare"
    assert result["authority"]["kemet"] == "decide_approve_execute_measure_audit"
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["human_approval_required"] is True
    assert result["commercial"]["revenue"] == "not_available"
    assert result["commercial"]["roi"] == "not_proven"
    assert result["commercial"]["causal_claim"] is False


def test_revenue_workforce_contract_fail_closed_for_missing_org():
    try:
        revenue_workforce_contract.build(
            organization_id=0,
            product={"name": "Kemet Demo Product"},
            qualification={"status": "qualified"},
        )
    except ValueError as exc:
        assert str(exc) == "organization_id_required"
    else:
        raise AssertionError("missing organization must fail closed")



def test_revenue_workforce_can_carry_evidence_references(monkeypatch):
    def fake_context(**kwargs):
        assert kwargs["organization_id"] == 1
        assert kwargs["query"] == "wallet pricing"
        return {
            "digest": "ctx-digest",
            "query_digest": "query-digest",
            "sources": [{
                "filename": "catalog.md",
                "chunk_index": 2,
                "content_digest": "source-digest",
            }],
            "retrieval": {"excluded": 0},
        }

    monkeypatch.setattr(
        "app.services.revenue_workforce_contract.evidence_backed_context_service.build",
        fake_context,
    )
    result = revenue_workforce_contract.build(
        organization_id=1,
        product={"name": "Leather Wallet"},
        qualification={"status": "qualified"},
        lead_id=6,
        channel="whatsapp",
        context_query="wallet pricing",
        task_id="commerce-task-1",
    )
    evidence = result["workflow"]["evidence_context"]
    assert evidence["digest"] == "ctx-digest"
    assert evidence["evidence_count"] == 1
    assert evidence["references"][0]["content_digest"] == "source-digest"
    assert result["governance"]["external_execution"] is False


def test_revenue_workforce_requires_context_pair():
    try:
        revenue_workforce_contract.build(
            organization_id=1,
            product={"name": "Wallet"},
            qualification={"status": "qualified"},
            context_query="pricing",
        )
    except ValueError as exc:
        assert str(exc) == "context_query_and_task_id_required"
    else:
        raise AssertionError("partial context input must fail closed")
