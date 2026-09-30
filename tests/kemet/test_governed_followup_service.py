from app.services.governed_followup_service import governed_followup_service


def test_qualified_followup_requires_human_approval():
    result = governed_followup_service.build_plan(
        organization_id=1,
        qualification={"status": "qualified", "missing_fields": [], "score": 90},
        channel="whatsapp", lead_id=6,
    )
    assert result["success"] is True
    assert result["status"] == "approval_required"
    assert result["action"] == "sales_follow_up"
    assert result["approval"]["required"] is True
    assert result["execution"]["executor"] == "kemet_canonical_runtime"
    assert result["execution"]["auto_execute"] is False


def test_unqualified_followup_is_blocked():
    result = governed_followup_service.build_plan(
        organization_id=1,
        qualification={"status": "needs_information", "missing_fields": ["budget"]},
    )
    assert result["status"] == "blocked"
    assert result["execution"]["external_execution"] is False


def test_invalid_channel_fails_closed():
    try:
        governed_followup_service.build_plan(
            organization_id=1,
            qualification={"status": "qualified", "missing_fields": []},
            channel="carrier_pigeon",
        )
    except ValueError as exc:
        assert str(exc) == "unsupported_followup_channel"
    else:
        raise AssertionError("unsupported channel must fail closed")


def test_commercial_claims_remain_conservative():
    result = governed_followup_service.build_plan(
        organization_id=1,
        qualification={"status": "qualified", "missing_fields": []},
    )
    assert result["commercial"]["revenue"] == "not_available"
    assert result["commercial"]["roi"] == "not_proven"
    assert result["commercial"]["causal_claim"] is False
