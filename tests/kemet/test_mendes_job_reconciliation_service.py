from wsgi import application
from app.services.mendes.mendes_job_reconciliation_service import mendes_job_reconciliation_service
from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service


def test_real_s1e1_reconciliation_preserves_canonical_and_history():
    with application.app_context():
        package = mendes_pilot_episode_service.build(1)["package"]
        report = mendes_job_reconciliation_service.report(1, package["package_digest"])
        assert report["status"] == "NO_DUPLICATE"
        assert report["canonical_job"] is None
        assert report["duplicate_jobs"] == []
        assert report["safe_action"] == "NONE"
        assert report["references"]["transition_rows_checked"] is True
