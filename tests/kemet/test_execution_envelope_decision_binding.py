from app.core.federation.execution_envelope import execution_envelope


def _fixture():
    authorization = {"plan_hash": "plan-hash", "plan_id": "plan-1"}
    envelope = execution_envelope.build(
        approval_package_hash="package-hash",
        decision_hash="decision-hash",
        handoff_hash="handoff-hash",
        authorization=authorization,
        execution_key="exec-1",
        provider_id="manus",
        action="manus.task.create",
        evidence_context_hash="evidence-hash",
        outcome_contract_digest="outcome-hash",
        artifact_preview_digest="artifact-hash",
    )
    return authorization, envelope


def test_execution_envelope_binds_decision_hash():
    authorization, envelope = _fixture()
    assert execution_envelope.verify(
        envelope,
        authorization=authorization,
        execution_key="exec-1",
        provider_id="manus",
        action="manus.task.create",
        decision_hash="decision-hash",
    )
    assert not execution_envelope.verify(
        envelope,
        authorization=authorization,
        execution_key="exec-1",
        provider_id="manus",
        action="manus.task.create",
        decision_hash="tampered-decision",
    )
