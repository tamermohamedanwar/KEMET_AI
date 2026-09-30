from app.services.production_intelligence import ProductionIntelligence
from app.services.production_critic_evidence import ProductionCriticEvidence
from app.services.production_trajectory_evaluation_gate import ProductionTrajectoryEvaluationGate


def _chain():
    pi = ProductionIntelligence()
    ce = ProductionCriticEvidence()
    trajectory = pi.trajectory(
        organization_id=7, project_id="film-1",
        events=[{"node_id": "qa", "kind": "qa", "status": "blocked", "evidence_digest": "qa-e"}],
        outcome={"status": "review"}, canonical_state_digest="state-1",
    )
    critic = ce.critic_evidence(
        organization_id=7, project_id="film-1", stage="qa", target_id="qa",
        trajectory_digest=trajectory["digest"],
        qa_evidence={"status": "BLOCKED", "digest": "qa-e"},
        observed={"continuity": "drift"}, expected={"continuity": "locked"},
        category="continuity", severity="high", finding="continuity drift",
        evidence_digests=["qa-e", "frame-e"],
        repair_recommendation={"action": "regenerate_shot", "stage_local": True},
    )
    binding = pi.bind_critic_to_trajectory(
        organization_id=7, project_id="film-1", trajectory=trajectory, critic=critic,
    )
    repair = ce.repair_evidence(
        organization_id=7, project_id="film-1", critic=critic,
        repair={"status": "verified"}, replay_digest="replay-1",
        paired_evaluation={"valid": True, "delta": {"qa": "improved"}},
    )
    gate = ProductionTrajectoryEvaluationGate()
    replay = gate.replay_evidence(
        organization_id=7, project_id="film-1", trajectory=trajectory,
        replay_digest="replay-1", replay_status="VERIFIED", output_digest="out-1",
        evidence_digests=["qa-e", "frame-e"],
    )
    paired = gate.paired_evaluation(
        organization_id=7, project_id="film-1", trajectory_digest=trajectory["digest"],
        replay=replay, baseline_digest="base-1", candidate_digest="cand-1", valid=True,
        metrics={"qa": {"before": 0.6, "after": 0.9}}, confidence=0.92,
        evidence_digests=["qa-e", "frame-e"],
    )
    evaluation_gate = gate.evaluate(
        organization_id=7, project_id="film-1", trajectory=trajectory, replay=replay,
        paired=paired, freshness={"status": "FRESH", "verified_at": "2026-09-20T02:00:00+03:00"},
    )
    eligibility = pi.learning_eligibility(
        organization_id=7, project_id="film-1", critic=critic, repair=repair,
        replay_digest="replay-1",
        paired_evaluation=paired,
        binding_digest=binding["digest"], evaluation_gate=evaluation_gate,
    )
    return pi, trajectory, critic, binding, repair, eligibility, evaluation_gate
def test_end_to_end_learning_loop_preserves_lineage_and_governance():
    pi, trajectory, critic, binding, repair, eligibility, evaluation_gate = _chain()
    proposal = pi.policy_proposal_from_eligibility(
        organization_id=7, project_id="film-1", stage="qa",
        patch={"rule": "require_continuity_lock_before_render"},
        eligibility=eligibility,
    )
    review = pi.build_policy_review_artifact(
        organization_id=7, project_id="film-1", proposal=proposal,
        learning_eligibility=eligibility,
    )
    assert review["review_status"] == "PENDING_HUMAN_REVIEW"
    assert review["decision_required_from_human"] is True
    assert review["execution_authority"] is False
    assert review["execution_gate_bypass"] is False
    decision = pi.record_policy_review_decision(
        organization_id=7, project_id="film-1", review_artifact=review,
        decision="APPROVED", approver_id=42,
    )
    assert decision["decision"] == "APPROVED"
    assert decision["authorization_issued"] is False
    assert decision["execution_authority"] is False
    assert decision["canonical_state_mutation"] is False
    impact = pi.record_policy_impact(
        organization_id=7, project_id="film-1", review_decision=decision,
        replay_digest="replay-1",
        post_replay_evaluation={"valid": True, "delta": {"qa": "improved"}},
        evaluation_gate=evaluation_gate,
    )
    assert impact["measured"] is True
    assert impact["learning_reusable"] is True
    assert impact["trajectory_digest"] == trajectory["digest"]
    assert impact["replay_digest"] == eligibility["replay_digest"]
    memory = pi.memory_from_policy_impact(
        organization_id=7, project_id="film-1", impact=impact,
        facts=[{"lesson": "continuity lock before render"}],
        invariants=[{"name": "continuity_lock", "required": True}],
    )
    graph_binding = pi.bind_policy_impact_to_graph(
        organization_id=7, project_id="film-1", impact=impact,
        trajectory=trajectory, memory=memory, stage="qa",
        evidence_digests=["qa-e", "frame-e", "replay-1"], confidence=0.92,
    )
    assert graph_binding["reuse_eligible"] is True
    assert graph_binding["memory_digest"] == memory["digest"]
    assert graph_binding["trajectory_digest"] == trajectory["digest"]
    specification = pi.specification(
        organization_id=7, project_id="film-1", scenes=[], shots=[], assets=[],
        constraints=[{"continuity_lock": True}],
    )
    reuse = pi.assess_memory_reuse(
        organization_id=7, project_id="film-1", memory=memory,
        binding=graph_binding, specification=specification,
        freshness={"status": "FRESH", "verified_at": "2026-09-20T02:00:00+03:00"},
    )
    from app.services.production_memory_activation_gate import production_memory_activation_gate
    activation_proposal = production_memory_activation_gate.propose(
        organization_id=7, project_id="film-1", memory=memory,
        lineage=memory["lineage"], reuse_assessment=reuse,
    )
    activation_decision = production_memory_activation_gate.decide(
        proposal=activation_proposal, approver_id=99, decision="APPROVED"
    )
    activation_record = production_memory_activation_gate.project(
        activation=activation_decision, memory=memory, lineage=memory["lineage"]
    )
    planning_projection = production_memory_activation_gate.planning_projection(
        activation_record=activation_record
    )
    lifecycle_status = production_memory_activation_gate.lifecycle_status(
        activation_record=activation_record, lineage=memory["lineage"],
        now="2026-09-20T02:00:00+03:00",
    )
    plan = pi.plan_context(
        organization_id=7, project_id="film-1", specification=specification,
        memory=memory, reuse_assessment=reuse,
        memory_planning_projection=planning_projection,
        memory_lifecycle_status=lifecycle_status,
    )
    assert plan["memory_planning_projection_digest"] == planning_projection["digest"]
    assert plan["memory_is_advisory"] is True
    assert plan["memory_reuse_assessment_digest"] == reuse["digest"]
    assert plan["memory_provenance"]["source_of_truth"] == memory["source_of_truth"]
    assert plan["memory_freshness"]["status"] == "FRESH"
    assert plan["authorization_issued"] is False
    assert plan["execution_authority"] is False
    assert plan["execution_gate_bypass"] is False
    assert plan["canonical_state_mutation"] is False
    assert plan["external_execution"] is False
    assert plan["governance"]["mcp"] is False
    assert binding["trajectory_digest"] == trajectory["digest"]
    assert critic["trajectory_digest"] == trajectory["digest"]
    assert repair["organization_id"] == eligibility["organization_id"] == 7
    assert proposal["trajectory_digest"] == trajectory["digest"]
    assert review["proposal_digest"] == proposal["digest"]
    assert decision["review_artifact_digest"] == review["digest"]
    assert impact["review_decision_digest"] == decision["digest"]
    assert memory["evidence_backed"] is True
    for blocked_status in ("RAW", "PENDING", "REJECTED", "STALE", "CONFLICTED", "REVOKED"):
        blocked = dict(lifecycle_status)
        blocked["status"] = blocked_status
        blocked["planning_visible"] = False
        try:
            pi.plan_context(
                organization_id=7, project_id="film-1", specification=specification,
                memory=memory, reuse_assessment=reuse,
                memory_planning_projection=planning_projection,
                memory_lifecycle_status=blocked,
            )
        except ValueError as exc:
            assert str(exc) == "memory_lifecycle_not_planning_visible"
        else:
            raise AssertionError(f"expected lifecycle block for {blocked_status}")


def test_learning_loop_rejects_weak_evidence_before_memory_reuse():
    pi, trajectory, critic, binding, repair, eligibility, evaluation_gate = _chain()
    impact = {"organization_id": 7, "project_id": "film-1", "digest": "impact-x", "trajectory_digest": trajectory["digest"], "measured": True, "learning_reusable": True, "replay_digest": "replay-1"}
    try:
        pi.memory_from_policy_impact(organization_id=7, project_id="film-1", impact=impact)
    except ValueError as exc:
        assert str(exc) == "evaluation_gate_provenance_required"
    else:
        raise AssertionError("ungated impact must not become reusable memory")


def test_learning_loop_rejects_stale_memory_before_planning():
    pi, trajectory, critic, binding, repair, eligibility, evaluation_gate = _chain()
    impact = {"organization_id": 7, "project_id": "film-1", "digest": "impact-y", "trajectory_digest": trajectory["digest"], "measured": True, "learning_reusable": True, "replay_digest": "replay-1"}
    try:
        pi.memory_from_policy_impact(organization_id=7, project_id="film-1", impact=impact)
    except ValueError as exc:
        assert str(exc) == "evaluation_gate_provenance_required"
    else:
        raise AssertionError("ungated impact must not reach memory freshness/planning")

