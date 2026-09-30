from app.services.production_learning_trace_gate import production_learning_trace_gate
from app.services.production_learning_trace_gate import ProductionLearningTraceGate
from tests.kemet.test_production_learning_loop_integration import _chain


def _artifacts():
    pi, trajectory, critic, binding, repair, eligibility, evaluation_gate = _chain()
    proposal = pi.policy_proposal_from_eligibility(
        organization_id=7, project_id="film-1", stage="qa",
        patch={"rule": "require_continuity_lock_before_render"}, eligibility=eligibility,
    )
    review = pi.build_policy_review_artifact(
        organization_id=7, project_id="film-1", proposal=proposal,
        learning_eligibility=eligibility,
    )
    decision = pi.record_policy_review_decision(
        organization_id=7, project_id="film-1", review_artifact=review,
        decision="APPROVED", approver_id=42,
    )
    impact = pi.record_policy_impact(
        organization_id=7, project_id="film-1", review_decision=decision,
        replay_digest="replay-1",
        post_replay_evaluation={"valid": True, "delta": {"qa": "improved"}},
        evaluation_gate=evaluation_gate,
    )
    replay = {"organization_id": 7, "project_id": "film-1", "replay_digest": "replay-1", "digest": "replay-artifact", "evidence_digests": ["qa-e", "frame-e"]}
    return pi, trajectory, critic, repair, replay, evaluation_gate, eligibility, review, decision, impact


def test_trace_is_integrated_with_real_learning_artifacts():
    pi, trajectory, critic, repair, replay, evaluation_gate, eligibility, review, decision, impact = _artifacts()
    paired = eligibility["paired_evaluation"]
    gate = production_learning_trace_gate.build_learning_trace(
        organization_id=7, project_id="film-1", correlation_id="film-1:qa:1",
        trajectory=trajectory, critic=critic, repair=repair, replay=replay,
        paired_evaluation=paired, evaluation_gate=evaluation_gate,
        review_decision=decision, impact=impact, eligibility=eligibility,
    )
    verified = production_learning_trace_gate.verify_learning_trace(
        organization_id=7, project_id="film-1", gate_artifact=gate,
    )
    assert verified["verified"] is True
    assert verified["event_count"] == 10
    assert gate["trace"]["governance"]["mcp"] is False
    assert gate["execution_authority"] is False
    assert gate["external_execution"] is False


def test_trace_gate_detects_tampering_and_tenant_mismatch():
    _, trajectory, critic, repair, replay, evaluation_gate, eligibility, _, decision, impact = _artifacts()
    gate = production_learning_trace_gate.build_learning_trace(
        organization_id=7, project_id="film-1", correlation_id="film-1:qa:2",
        trajectory=trajectory, critic=critic, repair=repair, replay=replay,
        paired_evaluation=eligibility["paired_evaluation"], evaluation_gate=evaluation_gate,
        review_decision=decision, impact=impact, eligibility=eligibility,
    )
    tampered = dict(gate)
    tampered["trace"] = dict(gate["trace"])
    tampered["trace"]["events"] = [dict(event) for event in gate["trace"]["events"]]
    tampered["trace"]["events"][4]["artifact_digest"] = "tampered"
    try:
        production_learning_trace_gate.verify_learning_trace(organization_id=7, project_id="film-1", gate_artifact=tampered)
    except ValueError as exc:
        assert str(exc) in {"trace_event_digest_invalid", "trace_digest_invalid"}
    else:
        raise AssertionError("tampered trace must be rejected")


def test_verified_trace_is_required_for_strict_policy_and_memory_paths():
    pi, trajectory, critic, repair, replay, evaluation_gate, eligibility, review, decision, impact = _artifacts()
    gate = production_learning_trace_gate.build_learning_trace(
        organization_id=7, project_id="film-1", correlation_id="film-1:qa:strict",
        trajectory=trajectory, critic=critic, repair=repair, replay=replay,
        paired_evaluation=eligibility["paired_evaluation"], evaluation_gate=evaluation_gate,
        review_decision=decision, impact=impact, eligibility=eligibility,
    )
    proposal = pi.policy_proposal_from_verified_learning(
        organization_id=7, project_id="film-1", stage="qa",
        patch={"rule": "require_continuity_lock_before_render"},
        eligibility=eligibility, verified_trace_gate=gate,
    )
    assert proposal["trace_verified"] is True
    assert proposal["learning_trace_digest"] == gate["trace_digest"]
    memory = pi.memory_from_verified_policy_impact(
        organization_id=7, project_id="film-1", impact=impact,
        verified_trace_gate=gate,
        facts=[{"lesson": "continuity lock before render"}],
    )
    assert memory["trace_verified"] is True
    assert memory["learning_trace_digest"] == gate["trace_digest"]


def test_verified_trace_strict_paths_reject_tampering_and_tenant_mismatch():
    pi, trajectory, critic, repair, replay, evaluation_gate, eligibility, review, decision, impact = _artifacts()
    gate = production_learning_trace_gate.build_learning_trace(
        organization_id=7, project_id="film-1", correlation_id="film-1:qa:strict-adversarial",
        trajectory=trajectory, critic=critic, repair=repair, replay=replay,
        paired_evaluation=eligibility["paired_evaluation"], evaluation_gate=evaluation_gate,
        review_decision=decision, impact=impact, eligibility=eligibility,
    )
    bad = dict(gate)
    bad["trace_digest"] = "tampered-trace"
    try:
        pi.memory_from_verified_policy_impact(organization_id=7, project_id="film-1", impact=impact, verified_trace_gate=bad)
    except ValueError as exc:
        assert str(exc) in {"trace_digest_invalid", "learning_trace_gate_digest_mismatch"}
    else:
        raise AssertionError("tampered trace must be rejected")
    try:
        pi.policy_proposal_from_verified_learning(organization_id=8, project_id="film-1", stage="qa", patch={}, eligibility=eligibility, verified_trace_gate=gate)
    except ValueError as exc:
        assert str(exc) == "learning_trace_binding_mismatch"
    else:
        raise AssertionError("cross-tenant trace must be rejected")
