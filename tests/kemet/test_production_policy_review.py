from app.services.production_intelligence import ProductionIntelligence


def _eligible():
    svc = ProductionIntelligence()
    eligibility = {
        "organization_id": 1, "project_id": "p",
        "learning_eligible": True, "policy_deployment_allowed": False,
        "trajectory_digest": "trajectory-1",
        "replay_digest": "replay-1",
        "paired_evaluation": {"valid": True, "delta": {"qa": "improved"}},
    }
    proposal = svc.policy_proposal_from_eligibility(
        organization_id=1, project_id="p", stage="qa",
        patch={"rule": "preserve_locked_reference"}, eligibility=eligibility
    )
    return svc, eligibility, proposal


def test_policy_review_artifact_is_human_gated():
    svc, eligibility, proposal = _eligible()
    review = svc.build_policy_review_artifact(
        organization_id=1, project_id="p",
        proposal=proposal, learning_eligibility=eligibility
    )
    assert review["review_status"] == "PENDING_HUMAN_REVIEW"
    assert review["decision_required_from_human"] is True
    assert review["approval_changes_status_only"] is True
    assert review["execution_gate_bypass"] is False


def test_policy_review_decision_never_issues_authorization():
    svc, eligibility, proposal = _eligible()
    review = svc.build_policy_review_artifact(
        organization_id=1, project_id="p",
        proposal=proposal, learning_eligibility=eligibility
    )
    decision = svc.record_policy_review_decision(
        organization_id=1, project_id="p",
        review_artifact=review, decision="APPROVED", approver_id=11
    )
    assert decision["status"] == "REVIEW_APPROVED"
    assert decision["authorization_issued"] is False
    assert decision["execution_authority"] is False
    assert decision["execution_gate_bypass"] is False


def test_policy_review_rejects_cross_tenant_and_invalid_decision():
    svc, eligibility, proposal = _eligible()
    review = svc.build_policy_review_artifact(
        organization_id=1, project_id="p",
        proposal=proposal, learning_eligibility=eligibility
    )
    try:
        svc.record_policy_review_decision(
            organization_id=2, project_id="p",
            review_artifact=review, decision="APPROVED", approver_id=11
        )
    except ValueError as exc:
        assert str(exc) == "review_tenant_mismatch"
    else:
        raise AssertionError("cross-tenant review must be rejected")

