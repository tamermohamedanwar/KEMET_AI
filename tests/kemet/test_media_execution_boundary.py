from app.core.approval_decision import decide_approval
from app.core.approval_package import ApprovalPackage
from app.core.execution.authorization import execution_authorization
from app.core.execution.execution_boundary import execution_boundary
from app.core.execution.runtime import canonical_execution_runtime
from app.services.media_approval_packet_service import media_approval_packet_service
from wsgi import application


def _packet():
    transcription = {
        "status": "transcribed",
        "transcript_digest": "a" * 64,
        "transcript": [{"start": 0.0, "end": 2.5, "text": "segment"}],
    }
    shortform = {
        "status": "planned",
        "organization_id": 1,
        "plan_digest": "b" * 64,
        "candidates": [{"index": 1, "start": 0.0, "duration": 2.5}],
    }
    return media_approval_packet_service.build(
        organization_id=1,
        task_id="media-boundary-001",
        transcription=transcription,
        shortform=shortform,
    )


def _approved(packet):
    data = packet["approval_package"]
    package = ApprovalPackage(
        organization_id=data["organization_id"],
        plan_hash=data["plan_hash"],
        context_fingerprint=data["context_fingerprint"],
        risk_level=data["risk_level"],
        risk_score=data["risk_score"],
        approval_required=data["approval_required"],
        external_side_effects=data["external_side_effects"],
        database_mutation=data["database_mutation"],
        affected_resources=tuple(data["affected_resources"]),
        reasons=tuple(data["reasons"]),
        evidence_requirements=tuple(data["evidence_requirements"]),
        package_hash=data["package_hash"],
        evidence_context_hash=data["evidence_context_hash"],
    )
    decision = decide_approval(package, approver_id=7, approved=True, reason="approved")
    plan = media_approval_packet_service._plan(
        1,
        "media-boundary-001",
        {"plan_digest": "b" * 64, "candidates": [{"index": 1, "start": 0.0, "duration": 2.5}]},
    ).as_dict()
    authorization = execution_authorization.create_authorization(plan, approver_id=7)
    handoff = media_approval_packet_service.create_gate_handoff(
        packet=packet, decision=decision, execution_key="media-boundary-001"
    )
    authorization["gate_handoff"] = handoff.as_dict()
    authorization["execution_key"] = "media-boundary-001"
    return plan, authorization


def test_execution_boundary_accepts_valid_media_handoff():
    packet = _packet()
    plan, authorization = _approved(packet)
    result = execution_boundary.require(
        plan, authorization, "shortform_candidate_selection"
    )
    assert result["allowed"] is True
    assert result["status"] == "authorized"
    assert result["executed"] is False


def test_execution_boundary_rejects_wrong_execution_key():
    packet = _packet()
    plan, authorization = _approved(packet)
    authorization["execution_key"] = "wrong-key"
    result = execution_boundary.require(
        plan, authorization, "shortform_candidate_selection"
    )
    assert result["allowed"] is False
    assert result["error"] == "gate_handoff_invalid"


def test_execution_boundary_rejects_wrong_action():
    packet = _packet()
    plan, authorization = _approved(packet)
    result = execution_boundary.require(plan, authorization, "external_publish")
    assert result["allowed"] is False
    assert result["error"] == "gate_handoff_invalid"


def test_execution_boundary_rejects_missing_handoff():
    packet = _packet()
    plan, authorization = _approved(packet)
    authorization.pop("gate_handoff")
    result = execution_boundary.require(
        plan, authorization, "shortform_candidate_selection"
    )
    assert result["allowed"] is False
    assert result["error"] == "gate_handoff_required"


def test_canonical_runtime_blocks_media_without_handoff_before_registry(monkeypatch):
    packet = _packet()
    plan, authorization = _approved(packet)
    authorization.pop("gate_handoff")
    calls = []
    class Registry:
        def exists(self, action):
            calls.append(("exists", action))
            return True
        def execute(self, *args, **kwargs):
            calls.append(("execute", args))
            return {"success": True}
    result = canonical_execution_runtime.execute(
        plan=plan,
        authorization=authorization,
        action_registry=Registry(),
        user_id=7,
    )
    assert result["success"] is False
    assert result["executed"] is False
    assert result["error"] == "gate_handoff_required"
    assert calls == []


def test_canonical_runtime_consumes_valid_media_authorization_once(monkeypatch):
    packet = _packet()
    plan, authorization = _approved(packet)
    calls = []
    class Registry:
        def exists(self, action):
            calls.append(("exists", action))
            return True
        def execute(self, action, parameters, user_id=None):
            calls.append(("execute", action))
            return {"success": True, "status": "completed", "executed": True}
    with application.app_context():
        first = canonical_execution_runtime.execute(
            plan=plan,
            authorization=authorization,
            action_registry=Registry(),
            user_id=7,
        )
        second = canonical_execution_runtime.execute(
            plan=plan,
            authorization=authorization,
            action_registry=Registry(),
            user_id=7,
        )
    assert first["success"] is True
    assert first["executed"] is True
    assert second["success"] is False
    assert second["executed"] is False
    assert second["error"] == "execution_authorization_used"
    assert calls.count(("execute", "shortform_candidate_selection")) == 1
