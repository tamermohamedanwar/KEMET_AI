from app.services.growth_experiment_proposal_service import growth_experiment_proposal_service


def test_proposes_only_from_reconciled_channel_evidence():
    result = growth_experiment_proposal_service.propose(
        organization_id=1,
        portfolio={"records": [
            {"content_id": "c1", "publication_id": "p1", "execution_key": "e1", "channel": "facebook", "eligible": True, "verified_revenue": 60, "qualified_views": 3000, "metric_evidence_digest": "m1"},
            {"content_id": "c2", "publication_id": "p2", "execution_key": "e2", "channel": "facebook", "eligible": True, "verified_revenue": 40, "qualified_views": 2000, "metric_evidence_digest": "m2"},
            {"content_id": "c3", "publication_id": "p3", "execution_key": "e3", "channel": "instagram", "eligible": False, "verified_revenue": 999, "qualified_views": 9000},
        ]},
    )
    assert len(result["proposals"]) == 1
    assert result["proposals"][0]["proposal"]["type"] == "controlled_growth_experiment"
    assert result["approval"]["required"] is True
    assert result["approval"]["execution_allowed"] is False


def test_rejects_invalid_organization():
    try:
        growth_experiment_proposal_service.propose(organization_id=0)
    except ValueError as exc:
        assert str(exc) == "organization_required"
    else:
        raise AssertionError("expected organization_required")
