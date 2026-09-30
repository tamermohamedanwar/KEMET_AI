from app.services.production_critic_evidence import ProductionCriticEvidence


def _critic():
    return ProductionCriticEvidence().critic_evidence(
        organization_id=1, project_id="p", stage="qa", target_id="shot-1",
        trajectory_digest="t1",
        qa_evidence={"status": "BLOCKED", "digest": "qa1"},
        observed={"continuity": "drift"}, expected={"continuity": "locked"},
        category="continuity", severity="high",
        finding="character continuity drift",
        evidence_digests=["qa1", "frame1"],
        repair_recommendation={"action": "regenerate_shot", "stage_local": True},
    )


def test_critic_evidence_is_deterministic_and_non_executing():
    svc = ProductionCriticEvidence()
    first = _critic()
    second = _critic()
    assert first["digest"] == second["digest"]
    assert first["learning_eligible"] is False
    assert first["governance"]["execution_authority"] is False
    assert first["governance"]["mcp"] is False


def test_critic_requires_evidence():
    try:
        ProductionCriticEvidence().critic_evidence(
            organization_id=1, project_id="p", stage="qa", target_id="s",
            trajectory_digest="t", qa_evidence={}, observed={}, expected={},
            category="x", severity="high", finding="x", evidence_digests=[],
        )
    except ValueError as exc:
        assert str(exc) == "critic_evidence_required"
    else:
        raise AssertionError("missing evidence must be rejected")


def test_repair_is_not_learning_eligible_without_replay():
    critic = _critic()
    out = ProductionCriticEvidence().repair_evidence(
        organization_id=1, project_id="p", critic=critic,
        repair={"status": "planned"},
    )
    assert out["learning_eligible"] is False
    assert out["policy_deployment_allowed"] is False
    assert out["repair_executed_by_contract"] is False


def test_repair_learning_requires_valid_paired_evaluation():
    critic = _critic()
    out = ProductionCriticEvidence().repair_evidence(
        organization_id=1, project_id="p", critic=critic,
        repair={"status": "verified"}, replay_digest="r1",
        paired_evaluation={"valid": True, "delta": {"qa": "improved"}},
    )
    assert out["learning_eligible"] is True
    assert out["governance"]["canonical_state_mutation"] is False

