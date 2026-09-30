from app.core.evidence.fabric import EvidenceFabric


def test_correlation_context_is_normalized_and_tenant_bound():
    fabric = EvidenceFabric()
    context = fabric.correlation_context(
        trace_id="trace-1", span_id="span-1", organization_id=7,
        task_id="task-1", approval_id="approval-1", execution_id="exec-1",
    )
    assert context["trace_id"] == "trace-1"
    assert context["organization_id"] == 7
    assert context["task_id"] == "task-1"
    assert context["execution_id"] == "exec-1"


def test_correlation_context_requires_trace_id():
    fabric = EvidenceFabric()
    try:
        fabric.correlation_context(trace_id="")
    except ValueError as exc:
        assert str(exc) == "trace_id_required"
    else:
        raise AssertionError("missing_trace_id_was_accepted")


def test_control_chain_is_deterministic_and_integrity_bound():
    fabric = EvidenceFabric()
    context = fabric.correlation_context(trace_id="trace-2", organization_id=9)
    stages = [
        {"stage": "decision", "status": "ready", "id": "d1"},
        {"stage": "approval", "status": "approved", "id": "a1"},
        {"stage": "execution", "status": "completed", "id": "e1"},
        {"stage": "evidence", "status": "verified", "id": "v1"},
        {"stage": "outcome", "status": "observed", "id": "o1"},
        {"stage": "learning", "status": "advisory", "id": "l1"},
    ]
    first = fabric.control_chain(correlation=context, stages=stages)
    second = fabric.control_chain(correlation=context, stages=stages)
    assert first["digest"] == second["digest"]
    assert first["type"] == "control_evidence_chain"
    assert [item["stage"] for item in first["stages"]] == [
        "decision", "approval", "execution", "evidence", "outcome", "learning"
    ]


def test_control_chain_rejects_unknown_stage():
    fabric = EvidenceFabric()
    context = fabric.correlation_context(trace_id="trace-3")
    try:
        fabric.control_chain(correlation=context, stages=[{"stage": "publish"}])
    except ValueError as exc:
        assert str(exc) == "unsupported_control_stage"
    else:
        raise AssertionError("unknown_stage_was_accepted")
