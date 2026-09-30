import pytest

from wsgi import application
from app.services.mendes.mendes_production_job_store import mendes_production_job_store


def _contracts(org=1):
    return ({"organization_id": org, "package_digest": "p" * 64, "script_digest": "s" * 64},
            {"organization_id": org, "contract_digest": "v" * 64, "script_digest": "s" * 64})


def test_durable_create_and_replay():
    package, voice = _contracts()
    with application.app_context():
        first = mendes_production_job_store.create(1, package, voice, ["rights"], idempotency_key="idem-store-replay-2")
        second = mendes_production_job_store.create(1, package, voice, ["rights"], idempotency_key="idem-store-replay-2")
        assert first["job_id"] == second["job_id"]
        assert second["replayed"] is True
        assert mendes_production_job_store.get(1, first["job_id"])["state"] == "PLANNED"


def test_durable_tenant_isolation():
    package, voice = _contracts(1)
    with application.app_context():
        job = mendes_production_job_store.create(1, package, voice, ["rights"], idempotency_key="idem-store-tenant-2")
        with pytest.raises(ValueError, match="production_job_not_found"):
            mendes_production_job_store.get(2, job["job_id"])


def test_same_package_different_workflow_creates_distinct_jobs():
    package, voice = _contracts()
    with application.app_context():
        production = mendes_production_job_store.create(1, package, voice, ["rights"], idempotency_key="same-key", workflow_purpose="production")
        readiness = mendes_production_job_store.create(1, package, voice, ["rights"], idempotency_key="same-key", workflow_purpose="readiness")
        assert production["job_id"] != readiness["job_id"]
        assert production["idempotency_key"] != readiness["idempotency_key"]
