from pathlib import Path

from app import create_app, db
from app.models.mendes_production_job import MendesProductionJobRecord, MendesProductionJobTransition
from app.services.mendes.mendes_controlled_production_service import mendes_controlled_production_service


def test_controlled_production_requires_explicit_approval():
    result = mendes_controlled_production_service.execute(1, False)
    assert result["success"] is False
    assert result["status"] == "BLOCKED"
    assert result["error"] == "production_approval_required"
    assert result["external_execution"] is False


def test_controlled_production_replays_verified_artifact_without_republishing():
    app = create_app()
    with app.app_context():
        before = {r.job_id for r in MendesProductionJobRecord.query.filter_by(organization_id=1).all()}
        try:
            result = mendes_controlled_production_service.execute(1, True)
            assert result["success"] is True
            assert result["status"] == "VERIFIED"
            assert result["production_job"]["state"] == "VERIFIED"
            artifact = result["artifact"]
            assert artifact["artifact_path"]
            assert Path(artifact["artifact_path"]).is_file()
            assert artifact["artifact_digest"]
            assert result["publication"]["ready"] is False
            assert result["publication"]["error"] == "publication_approval_required"
            assert result["measurement"]["views"] is None
            assert result["measurement"]["qualified_views"] is None
            assert result["measurement"]["revenue"] is None
            assert result["governance"]["external_execution"] is False
            assert result["governance"]["auto_publish"] is False
            assert result["governance"]["mcp"] is False
        finally:
            created = MendesProductionJobRecord.query.filter_by(organization_id=1).all()
            new_ids = {r.job_id for r in created} - before
            for transition in MendesProductionJobTransition.query.filter_by(organization_id=1).all():
                if transition.job_id in new_ids:
                    db.session.delete(transition)
            for record in created:
                if record.job_id in new_ids:
                    db.session.delete(record)
            db.session.commit()


def test_controlled_production_verification_is_deterministic():
    artifact = {"artifact_path": "/tmp/missing", "artifact_digest": "x", "artifact_ref": {"package_digest": "abc"}, "scene_count": 6}
    package = {"scenes": [{}, {}, {}, {}, {}, {}]}
    result = mendes_controlled_production_service._verify_artifact(artifact, package, "abc")
    assert result["verified"] is False
    assert result["checks"]["exists"] is False
    assert result["verification_digest"]
