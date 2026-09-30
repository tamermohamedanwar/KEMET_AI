from app.services.production_backlot_service import production_backlot_service


def test_backlot_unifies_production_distribution_and_economics():
    snapshot = production_backlot_service.snapshot(1)
    assert snapshot["mode"] == "production_backlot"
    assert snapshot["project"]["world"] == "Mendes World"
    assert len(snapshot["pipeline"]["stages"]) >= 8
    assert len(snapshot["distribution"]["channels"]) >= 11
    assert "snapchat" in {x["channel_id"] for x in snapshot["distribution"]["channels"]}
    assert snapshot["governance"]["canonical_runtime_only"] is True


def test_backlot_binds_real_production_job_identity_and_state():
    from app.services.mendes.mendes_production_job_service import mendes_production_job_service
    package = {"organization_id": 1, "package_digest": "pkg-1", "script_digest": "script-1"}
    voice = {"organization_id": 1, "script_digest": "script-1", "contract_digest": "voice-1"}
    job = mendes_production_job_service.create(1, package, voice, ["creative", "rights"], idempotency_key="idem-1")
    snapshot = production_backlot_service.snapshot(1, job=job)
    bound = snapshot["production_job"]
    assert bound["status"] == "bound"
    assert bound["state"] == "PLANNED"
    assert bound["job_digest"] == job["job_digest"]
    assert bound["idempotency_key"].startswith("mendes:production:")
    assert snapshot["pipeline"]["state"] == "planned"


def test_backlot_rejects_cross_tenant_job_binding():
    from app.services.mendes.mendes_production_job_service import mendes_production_job_service
    package = {"organization_id": 2, "package_digest": "pkg-2", "script_digest": "script-2"}
    voice = {"organization_id": 2, "script_digest": "script-2", "contract_digest": "voice-2"}
    job = mendes_production_job_service.create(2, package, voice, ["rights"], idempotency_key="idem-2")
    try:
        production_backlot_service.snapshot(1, job=job)
    except ValueError as exc:
        assert str(exc) == "production_job_tenant_mismatch"
    else:
        raise AssertionError("cross-tenant production job accepted")
