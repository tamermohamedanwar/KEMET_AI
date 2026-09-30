from app.core.federation.outcome_control import OutcomeControlError, OutcomeControlService


def _decision():
    return {"decision_id": "decision-1", "task_id": "task-1", "organization_id": 7, "digest": "d" * 64}


def test_contract_is_deterministic_and_governed():
    service = OutcomeControlService()
    first = service.contract(decision=_decision(), expected_metrics=[{"metric": "revenue", "baseline": 100, "target": 150}])
    second = service.contract(decision=_decision(), expected_metrics=[{"metric": "revenue", "baseline": 100, "target": 150}])
    assert first == second
    assert first["governance"]["causal_claim"] is False
    assert first["auto_execute"] is False
    assert len(first["digest"]) == 64


def test_measurement_evaluates_target_without_causal_claim():
    service = OutcomeControlService()
    contract = service.contract(decision=_decision(), expected_metrics=[{"metric": "revenue", "baseline": 100, "target": 150}])
    report = service.measure(contract, {"revenue": 160})
    assert report["results"][0]["delta"] == 60
    assert report["results"][0]["target_met"] is True
    assert report["governance"]["causal_claim"] is False


def test_missing_decision_fails_closed():
    try:
        OutcomeControlService().contract(decision={})
    except OutcomeControlError as exc:
        assert str(exc) == "decision_id_required"
    else:
        raise AssertionError("decision identity must be required")


def test_tampered_contract_fails_closed():
    service = OutcomeControlService()
    contract = service.contract(decision=_decision(), expected_metrics=[{"metric": "revenue", "baseline": 100, "target": 150}])
    contract["expected_metrics"][0]["target"] = 999
    try:
        service.measure(contract, {"revenue": 160})
    except OutcomeControlError as exc:
        assert str(exc) == "outcome_contract_integrity_mismatch"
    else:
        raise AssertionError("tampered outcome contract must fail closed")


def test_cross_tenant_observation_fails_closed():
    service = OutcomeControlService()
    contract = service.contract(decision=_decision(), expected_metrics=[{"metric": "revenue", "baseline": 100, "target": 150}])
    try:
        service.measure(contract, {"organization_id": 8, "revenue": 160})
    except OutcomeControlError as exc:
        assert str(exc) == "outcome_observation_tenant_mismatch"
    else:
        raise AssertionError("cross-tenant outcome observation must fail closed")
