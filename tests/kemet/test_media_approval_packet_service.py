from app.services.media_approval_packet_service import media_approval_packet_service


def _inputs():
    transcription = {
        "status": "transcribed",
        "transcript_digest": "a" * 64,
        "transcript": [
            {"start": 0.0, "end": 2.5, "text": "first segment"},
            {"start": 3.0, "end": 6.0, "text": "second segment"},
        ],
    }
    shortform = {
        "status": "planned",
        "organization_id": 1,
        "plan_digest": "b" * 64,
        "candidates": [
            {"index": 1, "start": 0.0, "duration": 6.0, "selection": "transcript_scored"}
        ],
    }
    return transcription, shortform


def test_build_binds_transcript_candidate_and_evidence():
    transcription, shortform = _inputs()
    packet = media_approval_packet_service.build(
        organization_id=1,
        task_id="media-test-001",
        transcription=transcription,
        shortform=shortform,
    )
    assert packet["schema"] == "kemet.media.approval_packet.v1"
    assert packet["transcription"]["digest"] == "a" * 64
    assert packet["shortform"]["digest"] == "b" * 64
    assert packet["approval"]["status"] == "PENDING_HUMAN_APPROVAL"
    assert packet["approval_package"]["approval_required"] is True
    assert packet["approval_package"]["external_side_effects"] is False
    assert packet["governance"]["execution_authority"] is False
    assert packet["governance"]["external_publication"] is False
    assert packet["governance"]["mcp"] is False
    assert len(packet["evidence_context"]["digest"]) == 64


def test_build_rejects_missing_timestamped_transcript():
    transcription, shortform = _inputs()
    transcription["transcript"] = []
    try:
        media_approval_packet_service.build(
            organization_id=1,
            task_id="media-test-002",
            transcription=transcription,
            shortform=shortform,
        )
    except ValueError as exc:
        assert str(exc) == "timestamped_transcript_required"
    else:
        raise AssertionError("approval packet accepted without timestamped transcript")


def test_build_rejects_cross_tenant_shortform():
    transcription, shortform = _inputs()
    shortform["organization_id"] = 2
    try:
        media_approval_packet_service.build(
            organization_id=1,
            task_id="media-test-003",
            transcription=transcription,
            shortform=shortform,
        )
    except ValueError as exc:
        assert str(exc) == "shortform_tenant_mismatch"
    else:
        raise AssertionError("cross-tenant shortform accepted")
def test_build_is_deterministic():
    transcription, shortform = _inputs()
    first = media_approval_packet_service.build(
        organization_id=1,
        task_id="media-test-004",
        transcription=transcription,
        shortform=shortform,
    )
    second = media_approval_packet_service.build(
        organization_id=1,
        task_id="media-test-004",
        transcription=transcription,
        shortform=shortform,
    )
    assert first["packet_digest"] == second["packet_digest"]
    assert first["approval_package"]["package_hash"] == second["approval_package"]["package_hash"]

from app.core.approval_decision import decide_approval
from app.services.media_approval_packet_service import media_approval_packet_service


def test_approved_media_packet_creates_central_gate_handoff():
    transcription, shortform = _inputs()
    packet = media_approval_packet_service.build(
        organization_id=1,
        task_id="media-gate-001",
        transcription=transcription,
        shortform=shortform,
    )
    package_data = packet["approval_package"]
    from app.core.approval_package import ApprovalPackage
    package = ApprovalPackage(
        organization_id=package_data["organization_id"],
        plan_hash=package_data["plan_hash"],
        context_fingerprint=package_data["context_fingerprint"],
        risk_level=package_data["risk_level"],
        risk_score=package_data["risk_score"],
        approval_required=package_data["approval_required"],
        external_side_effects=package_data["external_side_effects"],
        database_mutation=package_data["database_mutation"],
        affected_resources=tuple(package_data["affected_resources"]),
        reasons=tuple(package_data["reasons"]),
        evidence_requirements=tuple(package_data["evidence_requirements"]),
        package_hash=package_data["package_hash"],
        evidence_context_hash=package_data["evidence_context_hash"],
    )
    decision = decide_approval(package, approver_id=7, approved=True, reason="approved for governed review")
    handoff = media_approval_packet_service.create_gate_handoff(
        packet=packet,
        decision=decision,
        execution_key="media-gate-001",
    )
    assert handoff.status == "approved_for_gate"
    assert handoff.organization_id == 1
    assert handoff.action == "shortform_candidate_selection"
    assert handoff.approver_id == 7
    assert handoff.package_hash == package.package_hash


def test_rejected_media_packet_cannot_create_gate_handoff():
    transcription, shortform = _inputs()
    packet = media_approval_packet_service.build(
        organization_id=1,
        task_id="media-gate-002",
        transcription=transcription,
        shortform=shortform,
    )
    from app.core.approval_package import ApprovalPackage
    package_data = packet["approval_package"]
    package = ApprovalPackage(
        organization_id=package_data["organization_id"],
        plan_hash=package_data["plan_hash"],
        context_fingerprint=package_data["context_fingerprint"],
        risk_level=package_data["risk_level"],
        risk_score=package_data["risk_score"],
        approval_required=package_data["approval_required"],
        external_side_effects=package_data["external_side_effects"],
        database_mutation=package_data["database_mutation"],
        affected_resources=tuple(package_data["affected_resources"]),
        reasons=tuple(package_data["reasons"]),
        evidence_requirements=tuple(package_data["evidence_requirements"]),
        package_hash=package_data["package_hash"],
        evidence_context_hash=package_data["evidence_context_hash"],
    )
    decision = decide_approval(package, approver_id=7, approved=False, reason="not ready")
    try:
        media_approval_packet_service.create_gate_handoff(
            packet=packet, decision=decision, execution_key="media-gate-002"
        )
    except ValueError as exc:
        assert str(exc) == "approval_verification_failed"
    else:
        raise AssertionError("rejected media packet reached central gate")
