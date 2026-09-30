from app.services.mendes.mendes_production_job_service import mendes_production_job_service


def _inputs(org=1):
    package = {"organization_id": org, "package_digest": "pkg-1", "script_digest": "script-1"}
    voice = {"organization_id": org, "script_digest": "script-1", "contract_digest": "voice-1"}
    return package, voice


def test_create_binds_tenant_digests_and_governance():
    package, voice = _inputs()
    job = mendes_production_job_service.create(1, package, voice, ["creative", "rights"], idempotency_key="idem-1")
    assert job["state"] == "PLANNED"
    assert job["episode_package_digest"] == "pkg-1"
    assert job["voice_contract_digest"] == "voice-1"
    assert job["governance"]["execution_authority"] is False


def test_create_rejects_tenant_mismatch():
    package, voice = _inputs(2)
    try:
        mendes_production_job_service.create(1, package, voice, ["rights"])
    except ValueError as exc:
        assert str(exc) == "episode_package_tenant_mismatch"
    else:
        raise AssertionError("tenant mismatch accepted")


def test_transition_requires_approval_and_blocks_illegal_moves():
    package, voice = _inputs()
    job = mendes_production_job_service.create(1, package, voice, ["rights"])
    try:
        mendes_production_job_service.transition(job, "APPROVED", approval=False)
    except ValueError as exc:
        assert str(exc) == "approval_required"
    else:
        raise AssertionError("approval bypassed")
    approved = mendes_production_job_service.transition(job, "APPROVED", approval=True)
    assert approved["state"] == "APPROVED"
    try:
        mendes_production_job_service.transition(approved, "VERIFIED", approval=True, evidence={"digest": "e"})
    except ValueError as exc:
        assert str(exc) == "illegal_state_transition"
    else:
        raise AssertionError("illegal transition accepted")


def test_transition_requires_assets_and_verification_evidence():
    package, voice = _inputs()
    job = mendes_production_job_service.create(1, package, voice, ["rights"])
    approved = mendes_production_job_service.transition(job, "APPROVED", approval=True)
    producing = mendes_production_job_service.transition(approved, "PRODUCING", approval=True)
    try:
        mendes_production_job_service.transition(producing, "PRODUCED")
    except ValueError as exc:
        assert str(exc) == "asset_reference_required"
    else:
        raise AssertionError("produced without assets")
    produced = dict(producing, asset_refs=[{"id": "asset-1"}])
    produced = mendes_production_job_service.transition(produced, "PRODUCED")
    try:
        mendes_production_job_service.transition(produced, "VERIFIED")
    except ValueError as exc:
        assert str(exc) == "verification_evidence_required"
    else:
        raise AssertionError("verified without evidence")


def test_replay_is_idempotent_and_payload_bound():
    package, voice = _inputs()
    job = mendes_production_job_service.create(1, package, voice, ["rights"], idempotency_key="idem-1")
    incoming = mendes_production_job_service.create(1, package, voice, ["rights"], idempotency_key="idem-1")
    result = mendes_production_job_service.replay(job, incoming)
    assert result["replayed"] is True
    tampered = dict(incoming, script_digest="tampered")
    try:
        mendes_production_job_service.replay(job, tampered)
    except ValueError as exc:
        assert str(exc) == "replay_payload_mismatch"
    else:
        raise AssertionError("tampered replay accepted")


def test_replay_rejects_cross_tenant_attempt():
    package, voice = _inputs()
    job = mendes_production_job_service.create(1, package, voice, ["rights"], idempotency_key="idem-1")
    incoming = dict(job, organization_id=2)
    try:
        mendes_production_job_service.replay(job, incoming)
    except ValueError as exc:
        assert str(exc) == "replay_tenant_mismatch"
    else:
        raise AssertionError("cross-tenant replay accepted")


def test_workflow_purpose_scopes_idempotency():
    package, voice = _inputs()
    production = mendes_production_job_service.create(1, package, voice, ["rights"], idempotency_key="same-operation", workflow_purpose="production")
    readiness = mendes_production_job_service.create(1, package, voice, ["rights"], idempotency_key="same-operation", workflow_purpose="readiness")
    assert production["idempotency_key"] != readiness["idempotency_key"]
    assert production["workflow_purpose"] == "production"
    assert readiness["workflow_purpose"] == "readiness"


def test_invalid_workflow_purpose_fails_closed():
    package, voice = _inputs()
    try:
        mendes_production_job_service.create(1, package, voice, ["rights"], workflow_purpose="publish")
    except ValueError as exc:
        assert str(exc) == "invalid_workflow_purpose"
    else:
        raise AssertionError("invalid workflow purpose accepted")
