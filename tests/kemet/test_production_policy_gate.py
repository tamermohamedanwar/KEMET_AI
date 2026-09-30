from app.services.production_intelligence import ProductionIntelligence


def test_policy_proposal_requires_learning_eligibility():
    svc = ProductionIntelligence()
    eligibility = {
        "organization_id": 1,
        "project_id": "p",
        "learning_eligible": True,
        "policy_deployment_allowed": False,
        "trajectory_digest": "trajectory-1",
        "replay_digest": "replay-1",
        "paired_evaluation": {"valid": True, "delta": {"qa": "improved"}},
    }
    proposal = svc.policy_proposal_from_eligibility(
        organization_id=1, project_id="p", stage="qa",
        patch={"rule": "preserve_locked_reference"},
        eligibility=eligibility,
    )
    assert proposal["auto_deploy"] is False
    assert proposal["human_approval_required"] is True
    assert proposal["governance"]["mcp"] is False


def test_policy_proposal_blocks_ineligible_learning():
    svc = ProductionIntelligence()
    eligibility = {
        "organization_id": 1,
        "project_id": "p",
        "learning_eligible": False,
        "policy_deployment_allowed": False,
        "trajectory_digest": "trajectory-1",
        "replay_digest": "replay-1",
        "paired_evaluation": {"valid": False},
    }
    try:
        svc.policy_proposal_from_eligibility(
            organization_id=1, project_id="p", stage="qa",
            patch={"rule": "bad"}, eligibility=eligibility
        )
    except ValueError as exc:
        assert str(exc) == "learning_not_eligible"
    else:
        raise AssertionError("ineligible learning must be blocked")

