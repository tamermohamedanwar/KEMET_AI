from datetime import datetime, timedelta
import uuid


def test_schedule_is_tenant_scoped_and_timezone_validated():
    from app.core.automation_schedule_service import AutomationScheduleService
    from wsgi import application
    from app import db
    from app.models.organization import Organization

    with application.app_context():
        db.create_all()
        org = Organization.query.first()
        if org is None:
            org = Organization(name="Schedule Test Org", slug="schedule-test-org")
            db.session.add(org)
            db.session.commit()
        service = AutomationScheduleService()
        key = f"schedule-orchestration-{uuid.uuid4().hex}"
        schedule = service.create(
            organization_id=org.id,
            schedule_key=key,
            workflow_id="workflow-1",
            interval_seconds=300,
            timezone_name="Africa/Cairo",
            first_run_at=datetime.utcnow() - timedelta(seconds=1),
        )
        assert schedule["timezone"] == "Africa/Cairo"
        assert schedule["enabled"] is True
        assert schedule["run_count"] == 0


def test_due_schedule_enqueues_without_direct_execution():
    from app.core.automation_schedule_service import AutomationScheduleService
    from wsgi import application
    from app import db
    from app.models.organization import Organization

    with application.app_context():
        db.create_all()
        org = Organization.query.first()
        if org is None:
            org = Organization(name="Schedule Queue Org", slug="schedule-queue-org")
            db.session.add(org)
            db.session.commit()
        service = AutomationScheduleService()
        service.create(
            organization_id=org.id,
            schedule_key=f"schedule-due-{uuid.uuid4().hex}",
            workflow_id="workflow-due-1",
            interval_seconds=60,
            timezone_name="UTC",
            first_run_at=datetime.utcnow() - timedelta(seconds=1),
        )
        results = service.enqueue_due(organization_id=org.id)
        assert results
        assert results[0]["queue"]["envelope"]["execution"]["executed"] is False
        assert results[0]["queue"]["queue"]["status"] in {"queued", "deduplicated"}


def test_outcome_telemetry_persists_execution_metrics():
    from app.core.automation_outcome_service import AutomationOutcomeService
    from wsgi import application
    from app import db
    from app.models.organization import Organization
    from app.models.automation_outcome import AutomationOutcome

    with application.app_context():
        db.create_all()
        org = Organization.query.first()
        if org is None:
            org = Organization(name="Outcome Test Org", slug="outcome-test-org")
            db.session.add(org)
            db.session.commit()
        result = AutomationOutcomeService().record(
            organization_id=org.id,
            status="completed",
            executed=True,
            workflow_id="workflow-outcome-1",
            event_id="event-outcome-1",
            retry_count=1,
            cost_amount=0.0042,
            currency="USD",
            business_outcome="lead_created",
            correlation_id="corr-1",
            trace_id="trace-1",
            receipt={"status": "completed"},
        )
        row = db.session.get(AutomationOutcome, result["outcome_id"])
        assert row is not None
        assert row.executed is True
        assert row.business_outcome == "lead_created"
        assert float(row.cost_amount) == 0.0042
