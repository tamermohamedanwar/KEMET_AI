from app.services.production_intelligence import ProductionIntelligence
from app.services.production_trajectory_evaluation_gate import ProductionTrajectoryEvaluationGate


def _approved():
    svc = ProductionIntelligence()
    return svc.record_policy_review_decision(
        organization_id=1, project_id="p",
        review_artifact={
            "organization_id": 1, "project_id": "p",
            "review_status": "PENDING_HUMAN_REVIEW",
            "proposal_digest": "proposal-1",
            "trajectory_digest": "trajectory-1",
            "digest": "review-1",
        },
        decision="APPROVED", approver_id=11,
    )


def _gate():
    gate = ProductionTrajectoryEvaluationGate()
    trajectory = {"schema": "kemet.production.trajectory.v1", "version": 1, "organization_id": 1, "project_id": "p", "digest": "trajectory-1"}
    replay = gate.replay_evidence(organization_id=1, project_id="p", trajectory=trajectory, replay_digest="replay-2", replay_status="VERIFIED", output_digest="out-2", evidence_digests=["e1", "e2"])
    paired = gate.paired_evaluation(organization_id=1, project_id="p", trajectory_digest="trajectory-1", replay=replay, baseline_digest="base", candidate_digest="cand", valid=True, metrics={"qa": 1}, confidence=0.92, evidence_digests=["e1", "e2"])
    return gate.evaluate(organization_id=1, project_id="p", trajectory=trajectory, replay=replay, paired=paired, freshness={"status": "FRESH", "verified_at": "2026-09-20T02:00:00+03:00"})


def test_policy_impact_requires_measured_post_replay_evaluation():
    svc = ProductionIntelligence()
    decision = _approved()
    impact = svc.record_policy_impact(
        organization_id=1, project_id="p",
        review_decision=decision,
        replay_digest="replay-2",
        post_replay_evaluation={"valid": True, "delta": {"qa": "improved"}},
        evaluation_gate=_gate(),
    )
    assert impact["measured"] is True
    assert impact["learning_reusable"] is True
    assert impact["canonical_state_mutation"] is False
    assert impact["policy_deployment_allowed"] is False


def test_policy_impact_cannot_be_created_from_rejected_review():
    svc = ProductionIntelligence()
    decision = _approved()
    decision["decision"] = "REJECTED"
    try:
        svc.record_policy_impact(
            organization_id=1, project_id="p",
            review_decision=decision,
            replay_digest="replay-2",
            post_replay_evaluation={"valid": True},
            evaluation_gate=_gate(),
        )
    except ValueError as exc:
        assert str(exc) == "review_not_approved"
    else:
        raise AssertionError("rejected policy cannot produce impact evidence")


def test_policy_impact_can_feed_reusable_memory_without_mutating_state():
    svc = ProductionIntelligence()
    decision = _approved()
    impact = svc.record_policy_impact(
        organization_id=1, project_id="p",
        review_decision=decision,
        replay_digest="replay-2",
        post_replay_evaluation={"valid": True, "delta": {"qa": "improved"}},
        evaluation_gate=_gate(),
    )
    memory = svc.memory_from_policy_impact(
        organization_id=1, project_id="p", impact=impact,
        facts=[{"lesson": "verified"}],
    )
    assert memory["evidence_backed"] is True
    assert memory["canonical_state_mutation"] is False



def test_policy_impact_binds_to_exact_trajectory_stage_and_memory():
    svc = ProductionIntelligence()
    trajectory = svc.trajectory(
        organization_id=1, project_id="p",
        events=[{"node_id": "qa", "kind": "qa", "status": "verified", "evidence_digest": "qa-e"}],
        outcome={"status": "replay"}, canonical_state_digest="state",
    )
    impact = {
        "organization_id": 1, "project_id": "p", "digest": "impact-1",
        "trajectory_digest": trajectory["digest"], "trajectory_stage": "qa",
        "measured": True, "learning_reusable": True,
        "policy_deployment_allowed": False, "canonical_state_mutation": False,
        "replay_digest": "replay-2", "evaluation_gate_digest": "gate-1",
    }
    memory = svc.memory_from_policy_impact(
        organization_id=1, project_id="p", impact=impact,
        facts=[{"lesson": "verified"}],
    )
    binding = svc.bind_policy_impact_to_graph(
        organization_id=1, project_id="p", impact=impact,
        trajectory=trajectory, memory=memory, stage="qa",
        evidence_digests=["qa-e", "replay-2"], confidence=0.90,
    )
    assert binding["reuse_eligible"] is True
    assert binding["trajectory_stage"] == "qa"
    assert binding["memory_digest"] == memory["digest"]


def test_memory_reuse_is_planning_advisory_only_and_thresholds_are_enforced():
    svc = ProductionIntelligence()
    trajectory = svc.trajectory(
        organization_id=1, project_id="p",
        events=[{"node_id": "qa", "kind": "qa", "status": "verified"}],
        outcome={"status": "replay"}, canonical_state_digest="state",
    )
    impact = {
        "organization_id": 1, "project_id": "p", "digest": "impact-2",
        "trajectory_digest": trajectory["digest"], "measured": True,
        "learning_reusable": True, "policy_deployment_allowed": False, "canonical_state_mutation": False,
        "replay_digest": "replay-3", "evaluation_gate_digest": "gate-3",
    }
    memory = svc.memory_from_policy_impact(
        organization_id=1, project_id="p", impact=impact,
    )
    binding = svc.bind_policy_impact_to_graph(
        organization_id=1, project_id="p", impact=impact,
        trajectory=trajectory, memory=memory, stage="qa",
        evidence_digests=["e1", "e2"], confidence=0.90,
    )
    specification = svc.specification(
        organization_id=1, project_id="p", scenes=[], shots=[], assets=[], constraints=[]
    )
    reuse = svc.assess_memory_reuse(
        organization_id=1, project_id="p", memory=memory,
        binding=binding, specification=specification,
        freshness={"status": "FRESH", "verified_at": "2026-09-20T01:00:00+03:00"},
    )
    assert reuse["planning_advisory"] is True
    assert reuse["freshness"]["status"] == "FRESH"
    assert reuse["execution_authority"] is False
    assert reuse["authorization_issued"] is False
    assert reuse["execution_gate_bypass"] is False
