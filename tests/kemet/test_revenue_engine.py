from app.core.revenue import RevenueEngine


def test_revenue_engine():
    result = RevenueEngine.analyze(
        leads=100,
        opportunities=20,
        customers=8,
        revenue=50000,
        pipeline_value=120000,
    )

    assert result["success"] is True
    assert result["engine"] == "kemet_revenue"
    assert result["metrics"]["conversion_rate"] == 20.0


def test_revenue_priority():
    result = RevenueEngine.analyze(
        leads=50,
        opportunities=5,
        pipeline_value=100000,
    )

    assert result["decision"]["priority"] == "high"
    assert result["decision"]["focus"] == "Convert pipeline into revenue"


def test_revenue_actions_are_governed():
    result = RevenueEngine.analyze(leads=10, opportunities=2)
    actions = RevenueEngine.build_actions(result)

    assert len(actions) == 1
    assert actions[0]["requires_approval"] is True


def test_revenue_decision_consumes_canonical_lead_intelligence():
    from types import SimpleNamespace
    from app.services.revenue_decision_service import RevenueDecisionService

    lead = SimpleNamespace(
        id=501,
        organization_id=7,
        tenant_id=7,
        company_name="Acme Egypt",
        email="sales@acme.eg",
        phone="201001234567",
        message="We need a proposal for a business automation platform.",
        source="website",
        status="new",
        estimated_value=1500,
        lead_score=0,
        created_at=None,
        updated_at=None,
        freshness_at=None,
        provenance={"source": "website"},
        qualification_status="new",
        next_follow_up_at=None,
    )

    result = RevenueDecisionService.decide(lead)

    assert result["score"] == 100
    assert result["priority"] == "critical"
    assert result["lead_intelligence"]["scoring"]["method"] == "evidence_weighted_v1"
    assert len(result["lead_intelligence"]["evidence_digest"]) == 64
    assert result["lead_intelligence"]["governance"]["external_execution"] is False
