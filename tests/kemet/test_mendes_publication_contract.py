from wsgi import application

from app.services.mendes.mendes_production_job_store import mendes_production_job_store
from app.services.mendes.mendes_publication_contract_service import mendes_publication_contract_service


def _verified_job(key):
    with application.app_context():
        package = {"organization_id": 1, "package_digest": key + "p", "script_digest": key + "s"}
        voice = {"organization_id": 1, "contract_digest": key + "v", "script_digest": key + "s"}
        job = mendes_production_job_store.create(1, package, voice, ["rights"], idempotency_key=key, asset_refs=[{"uri": "asset:test"}])
        job = mendes_production_job_store.transition(1, job["job_id"], "APPROVED", approval=True)
        job = mendes_production_job_store.transition(1, job["job_id"], "PRODUCING", approval=True)
        job = mendes_production_job_store.transition(1, job["job_id"], "PRODUCED")
        return mendes_production_job_store.transition(1, job["job_id"], "VERIFIED", evidence={"evidence": "verified"})


def test_publication_requires_verified_production():
    with application.app_context():
        package = {"organization_id": 1, "package_digest": "cp", "script_digest": "cs"}
        voice = {"organization_id": 1, "contract_digest": "cv", "script_digest": "cs"}
        job = mendes_production_job_store.create(1, package, voice, ["rights"], idempotency_key="publication-unverified-1", asset_refs=[{"uri": "asset:test"}])
        result = mendes_publication_contract_service.validate(organization_id=1, production_job_id=job["job_id"], approval=True)
        assert result["error"] == "verified_production_required"


def test_publication_requires_explicit_approval():
    job = _verified_job("publication-approval-1")
    result = mendes_publication_contract_service.validate(organization_id=1, production_job_id=job["job_id"], approval=False)
    assert result["error"] == "publication_approval_required"


def test_publication_binds_verified_job_and_evidence():
    job = _verified_job("publication-valid-1")
    with application.app_context():
        result = mendes_publication_contract_service.validate(organization_id=1, production_job_id=job["job_id"], approval=True)
    assert result["ready"] is True
    assert result["production_job_digest"] == job["job_digest"]
    assert result["canonical_runtime_only"] is True
    assert result["execution_authority"] is False
