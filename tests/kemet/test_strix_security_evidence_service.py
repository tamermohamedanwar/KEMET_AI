from app.services.strix_security_evidence_service import StrixSecurityEvidenceService


def test_finding_requires_authorized_same_tenant_target():
    service = StrixSecurityEvidenceService()
    finding = {"finding_id": "F-1", "target_id": "staging-1", "severity": "high", "status": "reproduced"}
    evidence = service.record_finding(
        organization_id=1,
        trace_id="trace-1",
        finding=finding,
        target_digest="a" * 64,
        authorization_evidence={"authorized": True, "organization_id": 1, "authorization_id": "AUTH-1"},
    )
    assert evidence["schema"] == "kemet.security.strix_finding.v1"
    assert evidence["governance"]["execution_authority"] == "none"
    assert evidence["provenance"]["schema"] == "kemet.provenance_lineage.v1"
    assert len(evidence["digest"]) == 64


def test_finding_rejects_missing_authorization():
    service = StrixSecurityEvidenceService()
    try:
        service.record_finding(
            organization_id=1,
            trace_id="trace-1",
            finding={"finding_id": "F-1", "target_id": "staging-1", "severity": "high", "status": "observed"},
            target_digest="a" * 64,
            authorization_evidence={"authorized": False, "organization_id": 1},
        )
    except ValueError as exc:
        assert str(exc) == "target_authorization_required"
    else:
        raise AssertionError("unauthorized finding was accepted")


def test_finding_rejects_cross_tenant_authorization():
    service = StrixSecurityEvidenceService()
    try:
        service.record_finding(
            organization_id=1,
            trace_id="trace-1",
            finding={"finding_id": "F-1", "target_id": "staging-1", "severity": "high", "status": "observed"},
            target_digest="a" * 64,
            authorization_evidence={"authorized": True, "organization_id": 2},
        )
    except ValueError as exc:
        assert str(exc) == "authorization_tenant_mismatch"
    else:
        raise AssertionError("cross-tenant authorization was accepted")


def test_validation_transition_and_record_are_fail_closed():
    service = StrixSecurityEvidenceService()
    assert service.validate_transition(current_status="observed", next_status="reproduced") is True
    record = service.build_validation_record(
        organization_id=1, trace_id="trace-2", finding_id="F-2", target_id="fixture-1",
        target_digest="b" * 64, current_status="reproduced", next_status="retest_passed",
        validation_evidence={"authorized": True, "organization_id": 1, "result": "fixed"},
    )
    assert record["schema"] == "kemet.security.strix_validation.v1"
    assert len(record["digest"]) == 64
    assert record["governance"]["execution_authority"] == "none"


def test_validation_rejects_invalid_transition():
    service = StrixSecurityEvidenceService()
    try:
        service.validate_transition(current_status="retest_passed", next_status="reproduced")
    except ValueError as exc:
        assert str(exc) == "invalid_finding_transition"
    else:
        raise AssertionError("invalid transition was accepted")
