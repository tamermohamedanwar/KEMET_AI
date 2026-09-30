from app.services.content_approval_packet_service import content_approval_packet_service
from app.services.content_experiment_production_service import content_experiment_production_service
from app.services.content_experiment_service import content_experiment_service
from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service


def _inputs():
    experiment = content_experiment_service.build(
        organization_id=1, content_id="mendes-001", title="Mendes",
        audience="viewers", hook="hook", story="story", cta="cta",
    )
    pilot = mendes_pilot_episode_service.build(1)["package"]
    brief = content_experiment_production_service.build_brief(
        experiment=experiment, pilot_package=pilot
    )
    result = {
        "organization_id": 1,
        "artifact": {"artifact_digest": "a" * 64},
        "verification": {
            "verified": True, "verification_digest": "b" * 64,
            "checks": {"exists": True, "sha256_matches": True},
        },
        "readiness": {
            "readiness_digest": "c" * 64,
            "binding": {"episode_package_digest": pilot["package_digest"]},
            "quality_gates": {"originality": "REVIEW_REQUIRED", "continuity": "PASS"},
            "rights_review": {
                "status": "REVIEW_REQUIRED",
                "checks": {"script_originality_status": True, "voice_clone_disabled": True},
                "external_assets": [],
            },
            "historical_review": {"status": "PASS"},
            "voice_review": {
                "status": "REVIEW_REQUIRED",
                "decision": "VOICE_PROVIDER_SELECTION_REQUIRED",
                "checks": {"provider_selected": False, "clone_disabled": True, "rights_attestation_required": True},
                "evidence_reference": {"source_type": "official_provider_documentation"},
                "strategies": [],
            },
        },
    }
    return experiment, brief, result


def test_packet_binds_all_content_evidence():
    experiment, brief, result = _inputs()
    packet = content_approval_packet_service.build(
        organization_id=1, experiment=experiment,
        production_brief=brief, production_result=result,
    )
    assert packet["experiment_digest"] == experiment["experiment_digest"]
    assert packet["production_digest"] == brief["production_digest"]
    assert packet["artifact_digest"] == "a" * 64
    assert packet["verification_digest"] == "b" * 64
    assert packet["evidence"]["quality"]["artifact_integrity"]["verified"] is True
    assert packet["approval"]["status"] == "PENDING_HUMAN_APPROVAL"
    assert packet["execution"]["external_publication"] is False
    assert len(packet["packet_digest"]) == 64


def test_packet_requires_verified_artifact():
    experiment, brief, result = _inputs()
    result["verification"]["verified"] = False
    try:
        content_approval_packet_service.build(
            organization_id=1, experiment=experiment,
            production_brief=brief, production_result=result,
        )
    except ValueError as exc:
        assert str(exc) == "artifact_verification_required"
    else:
        raise AssertionError("unverified artifact entered approval packet")


def test_packet_rejects_cross_tenant_binding():
    experiment, brief, result = _inputs()
    result["organization_id"] = 2
    try:
        content_approval_packet_service.build(
            organization_id=1, experiment=experiment,
            production_brief=brief, production_result=result,
        )
    except ValueError as exc:
        assert str(exc) == "production_tenant_mismatch"
    else:
        raise AssertionError("cross-tenant approval packet accepted")


def test_packet_never_grants_execution_authority():
    experiment, brief, result = _inputs()
    packet = content_approval_packet_service.build(
        organization_id=1, experiment=experiment,
        production_brief=brief, production_result=result,
    )
    assert packet["execution"] == {
        "execution_authority": False,
        "external_publication": False,
        "auto_publish": False,
        "spend_authority": False,
    }
    assert packet["governance"]["mcp"] is False
