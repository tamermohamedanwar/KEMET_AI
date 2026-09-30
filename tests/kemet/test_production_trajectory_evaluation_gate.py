from app.services.production_trajectory_evaluation_gate import ProductionTrajectoryEvaluationGate
from app.services.production_intelligence import ProductionIntelligence


def _base():
    pi = ProductionIntelligence()
    gate = ProductionTrajectoryEvaluationGate()
    trajectory = pi.trajectory(
        organization_id=9, project_id="eval-1",
        events=[{"node_id": "qa", "kind": "qa", "status": "verified", "evidence_digest": "e1"}],
        outcome={"status": "replay"}, canonical_state_digest="state-1",
    )
    replay = gate.replay_evidence(
        organization_id=9, project_id="eval-1", trajectory=trajectory,
        replay_digest="replay-verified", replay_status="VERIFIED",
        output_digest="out-1", evidence_digests=["e1", "e2"],
    )
    paired = gate.paired_evaluation(
        organization_id=9, project_id="eval-1", trajectory_digest=trajectory["digest"],
        replay=replay, baseline_digest="baseline-1", candidate_digest="candidate-1",
        valid=True, metrics={"qa": {"before": 0.6, "after": 0.9}},
        confidence=0.93, evidence_digests=["e2", "e3"],
    )
    freshness = {"status": "FRESH", "verified_at": "2026-09-20T02:30:00+03:00"}
    return gate, trajectory, replay, paired, freshness


def test_evaluation_gate_proves_full_lineage_and_boundaries():
    gate, trajectory, replay, paired, freshness = _base()
    out = gate.evaluate(
        organization_id=9, project_id="eval-1", trajectory=trajectory,
        replay=replay, paired=paired, freshness=freshness,
    )
    assert out["learning_eligible"] is True
    assert out["trajectory_digest"] == trajectory["digest"]
    assert out["replay_digest"] == replay["replay_digest"]
    assert out["paired_evaluation_digest"] == paired["digest"]
    assert out["confidence"] == 0.93
    assert len(out["evidence_digests"]) >= 2
    assert out["policy_deployment_allowed"] is False
    assert out["execution_authority"] is False
    assert out["canonical_state_mutation"] is False
    assert out["governance"]["mcp"] is False


def test_evaluation_gate_rejects_low_confidence():
    gate, trajectory, replay, paired, freshness = _base()
    paired["confidence"] = 0.50
    try:
        gate.evaluate(organization_id=9, project_id="eval-1", trajectory=trajectory,
                      replay=replay, paired=paired, freshness=freshness)
    except ValueError as exc:
        assert str(exc) == "evaluation_confidence_threshold_not_met"
    else:
        raise AssertionError("low confidence must be blocked")


def test_evaluation_gate_rejects_stale_evidence():
    gate, trajectory, replay, paired, freshness = _base()
    freshness["status"] = "STALE"
    try:
        gate.evaluate(organization_id=9, project_id="eval-1", trajectory=trajectory,
                      replay=replay, paired=paired, freshness=freshness)
    except ValueError as exc:
        assert str(exc) == "evaluation_freshness_not_verified"
    else:
        raise AssertionError("stale evidence must be blocked")
def test_evaluation_gate_rejects_broken_replay_lineage():
    gate, trajectory, replay, paired, freshness = _base()
    paired["replay_digest"] = "wrong-replay"
    try:
        gate.evaluate(organization_id=9, project_id="eval-1", trajectory=trajectory,
                      replay=replay, paired=paired, freshness=freshness)
    except ValueError as exc:
        assert str(exc) == "replay_lineage_mismatch"
    else:
        raise AssertionError("broken replay lineage must be blocked")


def test_replay_contract_requires_verified_output_evidence():
    gate, trajectory, _, _, _ = _base()
    try:
        gate.replay_evidence(
            organization_id=9, project_id="eval-1", trajectory=trajectory,
            replay_digest="r", replay_status="FAILED", output_digest="",
            evidence_digests=[],
        )
    except ValueError as exc:
        assert str(exc) in {"replay_evidence_required", "replay_not_verified"}
    else:
        raise AssertionError("incomplete replay evidence must be blocked")
