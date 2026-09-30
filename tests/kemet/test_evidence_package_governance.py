from app.core.approval_package import build_approval_package
from app.core.evidence import execution_evidence_fabric
from app.core.federation.execution_envelope import execution_envelope
from app.core.plan_risk import PlanRiskAssessment


class FakePlan:
    organization_id = 7


def assessment():
    return PlanRiskAssessment(
        level="high",
        score=80,
        approval_required=True,
        external_side_effects=True,
        database_mutation=False,
        affected_resources=("project",),
        reasons=("automation",),
        assessment_hash="assessment-1",
    )


def binding():
    return {"organization_id": 7, "plan_hash": "plan-1", "context_fingerprint": "ctx-1"}


def test_context_evidence_package_is_deterministic():
    kwargs = dict(task_id="task-1", organization_id=7, policy={"fingerprint": "p1"}, routing={"provider_id": "openai"})
    first = execution_evidence_fabric.context_package(**kwargs)
    second = execution_evidence_fabric.context_package(**kwargs)
    assert first["digest"] == second["digest"]


def test_evidence_context_hash_changes_approval_package():
    first = build_approval_package(FakePlan(), binding(), assessment(), evidence_context_hash="e1")
    second = build_approval_package(FakePlan(), binding(), assessment(), evidence_context_hash="e2")
    assert first.package_hash != second.package_hash
    assert first.evidence_context_hash == "e1"


def test_execution_envelope_binds_evidence_context():
    authorization = {"plan_hash": "plan-1", "plan_id": "plan-id"}
    envelope = execution_envelope.build(
        approval_package_hash="pkg-1", decision_hash="dec-1", handoff_hash="handoff-1",
        authorization=authorization, execution_key="task-1", provider_id="kemet",
        action="business_insights", evidence_context_hash="evidence-1",
    )
    assert execution_envelope.verify(
        envelope, authorization=authorization, execution_key="task-1", provider_id="kemet",
        action="business_insights", evidence_context_hash="evidence-1",
    )
    assert not execution_envelope.verify(
        envelope, authorization=authorization, execution_key="task-1", provider_id="kemet",
        action="business_insights", evidence_context_hash="tampered",
    )
