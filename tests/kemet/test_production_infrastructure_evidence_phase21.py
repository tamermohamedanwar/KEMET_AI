import json
from pathlib import Path

from ops.production_infrastructure_evidence_phase21 import (
    OUTPUT,
    canonical_digest,
    capacity_evidence,
    database_evidence,
    evidence_matrix,
    process_snapshot,
    slo_contract,
)


def test_phase21_output_schema_and_blocked_state():
    data = json.loads(OUTPUT.read_text())
    assert data["schema"] == "kemet.production_infrastructure_evidence.v1"
    assert data["status"] == "BLOCKED"
    assert data["production_claim"] is False


def test_governance_is_read_only_and_non_mcp():
    data = json.loads(OUTPUT.read_text())
    governance = data["governance"]
    assert governance["read_only"] is True
    assert governance["execution_authority"] is False
    assert governance["external_execution"] is False
    assert governance["mcp"] is False
    assert governance["fail_closed"] is True


def test_database_does_not_expose_secret():
    data = database_evidence()
    assert data["secret_value_exposed"] is False
    assert "url" not in data


def test_capacity_evidence_is_non_production():
    data = capacity_evidence()
    assert data["available"] is True
    assert data["production_claim"] is False
    assert data["production_like"] is False


def test_required_matrix_remains_blocked_without_real_evidence():
    matrix = evidence_matrix()
    assert all(item["required"] for item in matrix.values())
    assert all(item["state"] == "BLOCKED" for item in matrix.values())


def test_slo_requires_explicit_acceptance():
    data = slo_contract()
    assert data["status"] == "PENDING_ACCEPTANCE"
    assert data["acceptance_owner"] is None
    assert data["targets_production_approved"] is False


def test_process_snapshot_has_no_capacity_or_pytest_workers():
    result = process_snapshot()
    assert result["available"] is True
    assert result["ok"] is True, result


def test_digest_is_reproducible_for_same_payload():
    data = json.loads(OUTPUT.read_text())
    digest = data["evidence_digest"]
    assert digest == canonical_digest(data)


def test_observability_chain_is_present():
    data = json.loads(OUTPUT.read_text())
    obs = data["observability"]
    assert obs["decision_chain"] == ["Decision", "Approval", "Execution", "Evidence", "Outcome", "Learning"]
    assert "trace_id" in obs["correlation_fields"]
    assert "evidence_id" in obs["correlation_fields"]
