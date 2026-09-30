from app.core.evidence.fabric import EvidenceFabric
from app.services.observability_control_fabric import observability_control_fabric
from app.services.reliability_slo import reliability_slo
from app.services.workforce_outcome_attribution_v2 import workforce_outcome_attribution_v2
from app.services.production_readiness_gate_v2 import production_readiness_gate_v2
from ops.architecture_consolidation import architecture_consolidation


def test_observability_redacts_and_correlates():
    event = observability_control_fabric.event(
        stage="execution", event_name="execution.finished",
        correlation={"trace_id": "t1", "organization_id": 7, "task_id": "task-1"},
        outcome="success", attributes={"api_key": "secret", "value": 1})
    assert event["attributes"]["api_key"] == "[REDACTED]"
    assert event["event_digest"]


def test_control_chain_is_deterministic():
    fabric = EvidenceFabric()
    correlation = {"trace_id": "t1", "organization_id": 7}
    stages = [{"stage": s, "status": "observed", "id": s + "-1"} for s in fabric_allowed()]
    a = fabric.control_chain(correlation=correlation, stages=stages)
    b = fabric.control_chain(correlation=correlation, stages=stages)
    assert a["digest"] == b["digest"]


def fabric_allowed():
    return ["decision", "approval", "execution", "evidence", "outcome", "learning"]


def test_slo_catalog_and_measurement():
    catalog = reliability_slo.catalog()
    assert catalog["measurement_only"] is True
    result = reliability_slo.evaluate({"successful_http_requests": 0.999, "requests_with_latency_le_1_5s": 0.98})
    assert any(item["name"] == "http_availability" and item["status"] == "MEETS" for item in result["results"])


def test_attribution_requires_identity_and_evidence():
    blocked = workforce_outcome_attribution_v2.build(
        organization_id=1, workforce_id="w", assignment_id="a", task_id="t",
        execution_id=None, evidence_id=None, observed_outcome=None)
    assert blocked["status"] == "IDENTITY_BOUND"
    observed = workforce_outcome_attribution_v2.build(
        organization_id=1, workforce_id="w", assignment_id="a", task_id="t",
        execution_id="e", evidence_id="ev", observed_outcome={"views": 10})
    assert observed["attribution"]["causal"] is False


def test_consolidation_requires_proof_before_delete():
    item = architecture_consolidation.classify(".", ["KEMET_AI_MASTER_HANDOFF_LATEST.md"])[0]
    assert item.classification == "ACTIVE_SUPPORT"
    assert architecture_consolidation.deletion_allowed(item, 0, False) is False


def test_production_gate_fails_closed():
    evidence = {key: {"ok": True} for key in production_readiness_gate_v2.REQUIRED}
    evidence["runtime"] = {"ok": False}
    result = production_readiness_gate_v2.evaluate(evidence)
    assert result["status"] == "BLOCKED"
    assert result["production_ready"] is False
    assert result["human_approval_required"] is True
