import pytest

from app.services.production_trace_integrity import ProductionTraceIntegrity


def _events():
    stages = ProductionTraceIntegrity.REQUIRED_STAGES
    return [
        {
            "stage": stage,
            "artifact_digest": f"artifact-{i}",
            "evidence_digests": ([f"evidence-{i}"] if stage in {"EVIDENCE", "EVALUATION", "QA", "REPLAY", "PAIRED_EVALUATION", "IMPACT", "LEARNING"} else []),
            "decision": "recorded",
            "actor_type": "system" if stage != "POLICY_REVIEW" else "human_approved",
            "policy_version": "policy.v1",
        }
        for i, stage in enumerate(stages)
    ]


def test_build_and_verify_immutable_causal_trace():
    svc = ProductionTraceIntegrity()
    trace = svc.build(organization_id=7, project_id="p1", correlation_id="corr-1", events=_events(), source_digests=["source-a"])
    result = svc.verify(trace)
    assert result["verified"] is True
    assert result["event_count"] == 10
    assert trace["governance"]["chain_of_thought_stored"] is False
    assert trace["governance"]["execution_authority"] is False


def test_tampering_is_detected():
    svc = ProductionTraceIntegrity()
    trace = svc.build(organization_id=7, project_id="p1", correlation_id="corr-1", events=_events())
    trace["events"][3]["decision"] = "tampered"
    with pytest.raises(ValueError, match="trace_event_digest_invalid"):
        svc.verify(trace)


def test_invalid_stage_order_is_blocked():
    svc = ProductionTraceIntegrity()
    events = _events()
    events[1], events[2] = events[2], events[1]
    with pytest.raises(ValueError, match="trace_stage_order_invalid"):
        svc.build(organization_id=7, project_id="p1", correlation_id="corr-1", events=events)


def test_evidence_is_required_for_evidence_bearing_stages():
    svc = ProductionTraceIntegrity()
    events = _events()
    events[1]["evidence_digests"] = []
    with pytest.raises(ValueError, match="trace_evidence_required"):
        svc.build(organization_id=7, project_id="p1", correlation_id="corr-1", events=events)
