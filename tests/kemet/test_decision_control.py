from app.core.federation.decision_control import DecisionControlError, DecisionControlService


def _brief():
    return {
        "digest": "b" * 64,
        "decision": {"recommendation": "Review the supported next step."},
        "traceability": {"research_evidence_digest": "e" * 64},
    }


def test_decision_record_is_deterministic_and_review_gated():
    service = DecisionControlService()
    first = service.create(task_id="task-1", organization_id=7, brief=_brief())
    second = service.create(task_id="task-1", organization_id=7, brief=_brief())
    assert first == second
    assert first["status"] == "review_required"
    assert first["human_review_required"] is True
    assert first["auto_execute"] is False
    assert first["governance"]["database_mutation"] is False
    assert first["evidence_digest"] == "e" * 64
    assert len(first["digest"]) == 64


def test_decision_record_fails_closed_without_identity_or_brief_digest():
    service = DecisionControlService()
    try:
        service.create(task_id="", organization_id=7, brief=_brief())
    except DecisionControlError as exc:
        assert str(exc) == "decision_identity_required"
    else:
        raise AssertionError("missing identity must fail closed")
    bad = _brief()
    bad.pop("digest")
    try:
        service.create(task_id="task-1", organization_id=7, brief=bad)
    except DecisionControlError as exc:
        assert str(exc) == "executive_brief_digest_required"
    else:
        raise AssertionError("missing brief digest must fail closed")
