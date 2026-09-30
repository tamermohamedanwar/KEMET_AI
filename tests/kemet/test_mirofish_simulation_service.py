from app.services.mirofish_simulation_service import mirofish_simulation_service


def test_mirofish_request_is_external_evidence_boundary():
    seed = "a" * 64
    request = mirofish_simulation_service.build_simulation_request(
        organization_id=1,
        content_id="mendes-001",
        seed_digest=seed,
        question="Compare audience reactions to three hooks.",
    )
    assert request["adapter"]["boundary"] == "external_governed_adapter"
    assert request["adapter"]["execution_authority"] is False
    assert request["simulation"]["external_execution"] is False
    assert request["evidence"]["must_not_be_presented_as_fact"] is True
    assert request["license"] == "AGPL-3.0"


def test_mirofish_evidence_is_reviewable_not_authoritative_prediction():
    request = mirofish_simulation_service.build_simulation_request(
        organization_id=1, content_id="mendes-001",
        seed_digest="b" * 64, question="Which hook is more engaging?"
    )
    evidence = mirofish_simulation_service.record_simulation_evidence(
        request=request,
        report_digest="c" * 64,
        findings=[{"scenario": "hook_a", "signal": "stronger"}],
        confidence=0.72,
    )
    assert evidence["status"] == "observed_simulation_evidence"
    assert evidence["not_a_fact"] is True
    assert evidence["not_a_prediction_guarantee"] is True
    assert evidence["execution_authority"] is False
