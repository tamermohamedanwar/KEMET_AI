from app.services.production_intelligence import ProductionIntelligence
from app.services.production_critic_evidence import ProductionCriticEvidence
from app.services.production_trajectory_evaluation_gate import ProductionTrajectoryEvaluationGate


def _fixture():
    pi = ProductionIntelligence()
    trajectory = pi.trajectory(
        organization_id=1, project_id="p",
        events=[{"node_id": "qa", "kind": "qa", "status": "blocked", "evidence_digest": "qa-e"}],
        outcome={"status": "review"}, canonical_state_digest="state"
    )
    critic = ProductionCriticEvidence().critic_evidence(
        organization_id=1, project_id="p", stage="qa", target_id="qa",
        trajectory_digest=trajectory["digest"],
        qa_evidence={"status": "BLOCKED", "digest": "qa-e"},
        observed={"continuity": "drift"}, expected={"continuity": "locked"},
        category="continuity", severity="high", finding="continuity drift",
        evidence_digests=["qa-e"],
        repair_recommendation={"action": "regenerate_shot", "stage_local": True},
    )
    return pi, trajectory, critic


def test_critic_binds_to_canonical_trajectory():
    pi, trajectory, critic = _fixture()
    out = pi.bind_critic_to_trajectory(
        organization_id=1, project_id="p",
        trajectory=trajectory, critic=critic
    )
    assert out["target_id"] == "qa"
    assert out["matched_events"][0]["node_id"] == "qa"
    assert out["learning_eligible"] is False
    assert out["governance"]["mcp"] is False


def test_learning_requires_verified_repair_and_valid_pair():
    pi, trajectory, critic = _fixture()
    repair = ProductionCriticEvidence().repair_evidence(
        organization_id=1, project_id="p", critic=critic,
        repair={"status": "verified"}, replay_digest="replay-1",
        paired_evaluation={"valid": True, "delta": {"qa": "improved"}},
    )
    binding = pi.bind_critic_to_trajectory(
        organization_id=1, project_id="p", trajectory=trajectory, critic=critic
    )
    gate = ProductionTrajectoryEvaluationGate()
    replay = gate.replay_evidence(organization_id=1, project_id="p", trajectory=trajectory, replay_digest="replay-1", replay_status="VERIFIED", output_digest="out-1", evidence_digests=["qa-e", "e2"])
    paired = gate.paired_evaluation(organization_id=1, project_id="p", trajectory_digest=trajectory["digest"], replay=replay, baseline_digest="base", candidate_digest="cand", valid=True, metrics={"qa": 1}, confidence=0.9, evidence_digests=["qa-e", "e2"])
    evaluation_gate = gate.evaluate(organization_id=1, project_id="p", trajectory=trajectory, replay=replay, paired=paired, freshness={"status": "FRESH", "verified_at": "2026-09-20T02:00:00+03:00"})
    out = pi.learning_eligibility(
        organization_id=1, project_id="p", critic=critic, repair=repair,
        replay_digest="replay-1",
        paired_evaluation=paired,
        binding_digest=binding["digest"], evaluation_gate=evaluation_gate,
    )
    assert out["learning_eligible"] is True
    assert out["policy_deployment_allowed"] is False
    assert out["canonical_state_mutation"] is False


def test_learning_rejects_invalid_pair():
    pi, trajectory, critic = _fixture()
    gate = ProductionTrajectoryEvaluationGate()
    replay = gate.replay_evidence(organization_id=1, project_id="p", trajectory=trajectory, replay_digest="replay-1", replay_status="VERIFIED", output_digest="out-1", evidence_digests=["qa-e", "e2"])
    try:
        gate.paired_evaluation(organization_id=1, project_id="p", trajectory_digest=trajectory["digest"], replay=replay, baseline_digest="base", candidate_digest="cand", valid=False, metrics={}, confidence=0.9, evidence_digests=["qa-e"])
    except ValueError as exc:
        assert str(exc) == "paired_evaluation_invalid"
    else:
        raise AssertionError("invalid pair must be blocked by evaluation gate")
