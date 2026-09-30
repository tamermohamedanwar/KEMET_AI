import pytest

from app.services.mendes.mendes_episode_readiness_service import mendes_episode_readiness_service
from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service


def _job(package):
    return {
        "job_id": "mendes-job-test",
        "organization_id": 1,
        "state": "PLANNED",
        "approval_state": "pending",
        "episode_package_digest": package["package_digest"],
        "script_digest": package["script_digest"],
        "voice_contract_digest": package["voice_contract"]["contract_digest"],
    }


def test_readiness_package_is_deterministic_and_review_gated():
    package = mendes_pilot_episode_service.build(1)["package"]
    a = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    b = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert a["readiness_digest"] == b["readiness_digest"]
    assert a["readiness_status"] == "REVIEW_REQUIRED"
    assert a["approval"]["status"] == "pending"
    assert a["governance"]["execution_authority"] is False
    assert a["governance"]["auto_publish"] is False


def test_readiness_preserves_fictional_classification():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["historical_review"]["status"] == "PASS"
    assert result["historical_review"]["historical_claim"] is False


def test_voice_and_budget_require_review_without_fabrication():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["voice_review"]["decision"] == "VOICE_PROVIDER_SELECTION_REQUIRED"
    assert result["budget_review"]["estimated_cost"] is None
    assert result["budget_review"]["verified_cost"] is None
    assert result["budget_review"]["actual_charge"] is None


def test_cross_tenant_and_digest_mismatch_fail_closed():
    package = mendes_pilot_episode_service.build(1)["package"]
    with pytest.raises(ValueError, match="readiness_tenant_mismatch"):
        mendes_episode_readiness_service.build(organization_id=2, job=_job(package), package=package)
    job = _job(package)
    job["script_digest"] = "x" * 64
    with pytest.raises(ValueError, match="script_digest_mismatch"):
        mendes_episode_readiness_service.build(organization_id=1, job=job, package=package)


def test_readiness_rejects_implicit_approval_or_execution_state():
    package = mendes_pilot_episode_service.build(1)["package"]
    job = _job(package)
    job["state"] = "APPROVED"
    with pytest.raises(ValueError, match="readiness_requires_planned_job"):
        mendes_episode_readiness_service.build(organization_id=1, job=job, package=package)
    package["approval"]["status"] = "approved"
    with pytest.raises(ValueError, match="readiness_requires_pending_approval"):
        mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)


def test_rights_passes_when_pilot_has_no_external_assets():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["rights_review"]["status"] == "PASS"
    assert result["rights_review"]["external_assets"] == []


def test_policy_review_passes_for_current_fictional_pilot():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["policy_review"]["status"] == "PASS"
    assert result["policy_review"]["checks"]["risk_signals_absent"] is True


def test_external_asset_without_provenance_requires_review():
    package = mendes_pilot_episode_service.build(1)["package"]
    package["external_assets"] = [{"asset_id": "asset-1", "source": "unknown"}]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["rights_review"]["status"] == "REVIEW_REQUIRED"
    assert "rights:no_external_assets_without_provenance" in result["review_required_items"]


def test_historical_claim_injection_is_blocked():
    package = mendes_pilot_episode_service.build(1)["package"]
    package["script"]["historical_claim"] = True
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["historical_review"]["status"] == "BLOCKED"


def test_voice_provider_selection_remains_explicit():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["voice_review"]["provider"] == "piper_local"
    assert result["voice_review"]["candidate_provider"] == "piper_local"
    assert result["voice_review"]["evidence"]["source_uri"] == "https://github.com/gyroing/piper-tts-for-termux"
    assert "voice:provider_selection_required" in result["review_required_items"]


def test_official_evidence_does_not_grant_voice_execution_authority():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["voice_review"]["checks"]["execution_authority"] is True
    assert result["governance"]["execution_authority"] is False


def test_budget_exposes_only_official_pricing_reference_and_unknowns():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    budget = result["budget_review"]
    assert budget["evidence"]["voice"]["pricing_status"] == "local_runtime_no_api_fee"
    assert budget["verified_cost"] is None
    assert budget["actual_charge"] is None
    assert budget["review_required_items"] == ["budget:provider_selection_required_for_verified_cost"]


def test_platform_evidence_distinguishes_verified_requirements_from_unverified_meta():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    evidence = result["platform_readiness"]["evidence"]
    assert evidence["youtube"]["source_uri"].startswith("https://support.google.com/")
    assert evidence["tiktok"]["source_uri"].startswith("https://developers.tiktok.com/")
    assert evidence["youtube"]["evidence_digest"]
    assert evidence["tiktok"]["evidence_digest"]
    assert evidence["instagram"]["source_uri"].startswith("https://www.facebook.com/help/instagram/")
    assert evidence["instagram"]["evidence_digest"]
    assert evidence["facebook"]["source_uri"].startswith("https://www.facebook.com/help/")
    assert evidence["facebook"]["evidence_digest"]
    assert result["readiness_status"] == "REVIEW_REQUIRED"


def test_budget_never_conflates_estimate_with_actual_charge():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    budget = result["budget_review"]
    assert budget["estimated_cost"] is None
    assert budget["verified_cost"] is None
    assert budget["actual_charge"] is None


def test_platform_review_never_grants_publish_authority():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["platform_readiness"]["status"] == "REVIEW_REQUIRED"
    assert "platform:publishing_approval_required" in result["review_required_items"]
    assert result["approval"]["publication"] == "NOT_REQUESTED"


def test_readiness_digest_changes_when_review_data_changes():
    package = mendes_pilot_episode_service.build(1)["package"]
    first = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    package["voice_contract"]["provider"] = "untrusted-test-provider"
    second = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert first["readiness_digest"] != second["readiness_digest"]


def test_execution_authority_cannot_be_granted_by_readiness_package():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["governance"]["execution_authority"] is False
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["auto_publish"] is False


def test_ready_for_approval_requires_no_review_items():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["readiness_status"] == "REVIEW_REQUIRED"
    assert result["review_required_items"]


def test_malformed_job_identity_fails_closed():
    package = mendes_pilot_episode_service.build(1)["package"]
    job = _job(package)
    job["job_id"] = ""
    with pytest.raises(ValueError):
        mendes_episode_readiness_service.build(organization_id=1, job=job, package=package)


def test_voice_contract_tampering_fails_closed():
    package = mendes_pilot_episode_service.build(1)["package"]
    job = _job(package)
    job["voice_contract_digest"] = "z" * 64
    with pytest.raises(ValueError, match="voice_contract_digest_mismatch"):
        mendes_episode_readiness_service.build(organization_id=1, job=job, package=package)


def test_package_digest_tampering_fails_closed():
    package = mendes_pilot_episode_service.build(1)["package"]
    job = _job(package)
    job["episode_package_digest"] = "x" * 64
    with pytest.raises(ValueError, match="episode_package_digest_mismatch"):
        mendes_episode_readiness_service.build(organization_id=1, job=job, package=package)


def test_job_organization_mismatch_fails_closed():
    package = mendes_pilot_episode_service.build(1)["package"]
    job = _job(package)
    job["organization_id"] = 2
    with pytest.raises(ValueError, match="readiness_tenant_mismatch"):
        mendes_episode_readiness_service.build(organization_id=1, job=job, package=package)


def test_approval_tampering_fails_closed():
    package = mendes_pilot_episode_service.build(1)["package"]
    job = _job(package)
    job["approval_state"] = "approved"
    with pytest.raises(ValueError, match="readiness_requires_pending_approval"):
        mendes_episode_readiness_service.build(organization_id=1, job=job, package=package)


def test_fake_external_asset_rights_cannot_be_marked_pass():
    package = mendes_pilot_episode_service.build(1)["package"]
    package["external_assets"] = [{"asset_id": "external-1", "license_status": "verified"}]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["rights_review"]["status"] == "REVIEW_REQUIRED"


def test_fake_budget_values_are_not_created_by_service():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert set(result["budget_review"]["categories"]) == set(mendes_episode_readiness_service.BUDGET_CATEGORIES)
    assert all(value["estimated_cost"] is None and value["verified_cost"] is None and value["actual_charge"] is None for value in result["budget_review"]["categories"].values())


def test_publish_authority_is_never_inferred_from_platform_configuration():
    package = mendes_pilot_episode_service.build(1)["package"]
    package["publishing_authority"] = {"youtube": True, "tiktok": True, "instagram": True, "facebook": True}
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["approval"]["publication"] == "NOT_REQUESTED"
    assert "platform:publishing_approval_required" in result["review_required_items"]


def test_readiness_digest_binds_job_identity_tenant_integrity_and_digest_integrity():
    package = mendes_pilot_episode_service.build(1)["package"]
    job = _job(package)
    job.update({
        "idempotency_key": "mendes:production:test-operation",
        "workflow_purpose": "production",
        "job_digest": "job-digest-1",
    })
    first = mendes_episode_readiness_service.build(organization_id=1, job=job, package=package)
    assert first["job_identity"]["idempotency_key"] == "mendes:production:test-operation"
    assert first["job_identity"]["workflow_purpose"] == "production"
    assert first["tenant_integrity"]["status"] == "PASS"
    assert first["digest_integrity"]["status"] == "PASS"
    assert first["critical_review_items"] == []
    job["job_digest"] = "tampered-job-digest"
    second = mendes_episode_readiness_service.build(organization_id=1, job=job, package=package)
    assert first["readiness_digest"] != second["readiness_digest"]


def test_current_official_voice_pricing_evidence_is_refreshed_for_selected_provider():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    voice = result["voice_review"]
    budget = result["budget_review"]
    assert voice["provider"] == "piper_local"
    assert voice["evidence"]["source_uri"] == "https://github.com/gyroing/piper-tts-for-termux"
    assert voice["evidence"]["pricing"] == "no_api_fee_local_runtime"
    assert voice["checks"]["no_api_fee"] is True
    assert budget["evidence"]["pricing"]["pricing_timestamp"] == "2026-09-19"
    assert budget["verified_cost"] is None
    assert budget["actual_charge"] is None


def test_current_platform_evidence_captures_publication_audit_and_ai_disclosure_boundaries():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    platforms = result["platform_readiness"]
    youtube = platforms["evidence"]["youtube"]
    tiktok = platforms["evidence"]["tiktok"]
    assert youtube["insert_uri"].startswith("https://developers.google.com/youtube/")
    assert "altered_or_synthetic_content_disclosure_when_required" in youtube["metadata_requirements"]
    assert "audit" in youtube["api_publication_note"]
    assert tiktok["source_uri"].endswith("direct-post")
    assert "is_aigc_when_applicable" in tiktok["metadata_requirements"]
    assert "audit" in tiktok["api_publication_note"]
    assert platforms["status"] == "REVIEW_REQUIRED"
    assert "platform:publishing_approval_required" in result["review_required_items"]


def test_readiness_digest_binds_governance_and_publication_state():
    package = mendes_pilot_episode_service.build(1)["package"]
    result = mendes_episode_readiness_service.build(organization_id=1, job=_job(package), package=package)
    assert result["governance"]["canonical_runtime_only"] is True
    assert result["approval"]["status"] == "pending"
    assert result["approval"]["publication"] == "NOT_REQUESTED"
    baseline = result["readiness_digest"]
    result["governance"]["auto_publish"] = True
    assert mendes_episode_readiness_service._digest({k: v for k, v in result.items() if k != "readiness_digest"}) != baseline
