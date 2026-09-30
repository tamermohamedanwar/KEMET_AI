from wsgi import application


def _admin_client():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    return client


def test_production_backlot_real_route_returns_business_payload():
    client = _admin_client()
    response = client.get("/command-center/api/bos/production-backlot?title=Hikayat%20Mendes")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    snapshot = body["production_backlot"]
    assert snapshot["project"]["title"] == "Hikayat Mendes"
    assert snapshot["project"]["world"] == "Mendes World"
    assert snapshot["project"]["series"] == "Hikayat Mendes"
    assert isinstance(snapshot["pipeline"]["stages"], list)
    assert snapshot["governance"]["human_approval_required"] is True
    assert snapshot["governance"]["canonical_runtime_only"] is True


def test_production_backlot_requires_authentication():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    response = client.get("/command-center/api/bos/production-backlot")
    assert response.status_code in {302, 401}


def test_production_job_preview_binds_job_to_backlot():
    client = _admin_client()
    response = client.post(
        "/command-center/api/bos/production-backlot/job-preview",
        json={
            "title": "Hikayat Mendes",
            "episode_package": {
                "organization_id": 1,
                "package_digest": "pkg-runtime",
                "script_digest": "script-runtime",
            },
            "voice_contract": {
                "organization_id": 1,
                "script_digest": "script-runtime",
                "contract_digest": "voice-runtime",
            },
            "quality_gates": ["creative", "rights"],
            "idempotency_key": "runtime-job-route-create-get-1",
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["executed"] is False
    assert body["production_job"]["state"] == "PLANNED"
    bound = body["production_backlot"]["production_job"]
    assert bound["status"] == "bound"
    assert bound["job_digest"] == body["production_job"]["job_digest"]
    assert bound["idempotency_key"].startswith("mendes:production:")
    assert body["production_backlot"]["governance"]["canonical_runtime_only"] is True


def test_production_job_route_create_get_and_transition():
    client = _admin_client()
    payload = {
        "episode_package": {"organization_id": 1, "package_digest": "p" * 64, "script_digest": "s" * 64},
        "voice_contract": {"organization_id": 1, "contract_digest": "v" * 64, "script_digest": "s" * 64},
        "quality_gates": ["rights", "creative"],
        "idempotency_key": "runtime-job-1",
    }
    created = client.post("/command-center/api/bos/production-backlot/job-preview", json=payload)
    assert created.status_code == 200
    job = created.get_json()["production_job"]
    assert job["state"] == "PLANNED"
    fetched = client.get(f"/command-center/api/bos/production-job/{job['job_id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["production_job"]["job_id"] == job["job_id"]
    bound_snapshot = client.get(f"/command-center/api/bos/production-backlot?job_id={job['job_id']}")
    assert bound_snapshot.status_code == 200
    assert bound_snapshot.get_json()["production_backlot"]["production_job"]["job_digest"] == job["job_digest"]
    transitioned = client.post(f"/command-center/api/bos/production-job/{job['job_id']}/transition", json={"target_state": "APPROVED", "approval": True})
    assert transitioned.status_code == 200
    assert transitioned.get_json()["production_job"]["state"] == "APPROVED"
    assert transitioned.get_json()["executed"] is False


def test_production_job_route_rejects_approval_bypass():
    client = _admin_client()
    payload = {
        "episode_package": {"organization_id": 1, "package_digest": "a" * 64, "script_digest": "b" * 64},
        "voice_contract": {"organization_id": 1, "contract_digest": "c" * 64, "script_digest": "b" * 64},
        "quality_gates": ["rights"], "idempotency_key": "runtime-job-bypass-2",
    }
    created = client.post("/command-center/api/bos/production-backlot/job-preview", json=payload)
    job_id = created.get_json()["production_job"]["job_id"]
    response = client.post(f"/command-center/api/bos/production-job/{job_id}/transition", json={"target_state": "APPROVED", "approval": False})
    assert response.status_code == 400
    assert response.get_json()["error"] == "approval_required"
