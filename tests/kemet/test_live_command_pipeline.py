import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_command_context_contains_live_business_data():
    from wsgi import application

    with application.app_context():
        from app.core.orchestration.command_center_wiring import (
            KemetCommandCenterWiring,
        )

        wiring = KemetCommandCenterWiring()

        context = wiring.build_command_context(
            organization_id=1,
            user_id=1,
            message="Analyze business performance",
        )

        assert context["organization_id"] == 1
        assert context["user_id"] == 1
        assert context["message"] == "Analyze business performance"

        assert context["mode"] == "advisory"
        assert context["approval_required"] is True
        assert context["external_execution"] is False
        assert context["database_mutation"] is False

        live = context["live_business"]

        assert live["organization_id"] == 1
        assert live["organization_name"] == "Default Organization"
        assert "revenue" in live
        assert "leads" in live
        assert "customers" in live
        assert "open_tickets" in live
        assert "automation_executions" in live


def test_command_context_is_tenant_scoped():
    from wsgi import application

    with application.app_context():
        from app.core.orchestration.command_center_wiring import (
            KemetCommandCenterWiring,
        )

        wiring = KemetCommandCenterWiring()

        context = wiring.build_command_context(
            organization_id=1,
            user_id=1,
            message="Show my business",
        )

        live = context["live_business"]

        assert live["organization_id"] == 1
        assert live["organization_name"] == "Default Organization"


def test_command_context_cannot_enable_external_execution():
    from wsgi import application

    with application.app_context():
        from app.core.orchestration.command_center_wiring import (
            KemetCommandCenterWiring,
        )

        wiring = KemetCommandCenterWiring()

        context = wiring.build_command_context(
            organization_id=1,
            user_id=1,
            message="Execute action",
        )

        assert context["external_execution"] is False
        assert context["database_mutation"] is False
        assert context["approval_required"] is True


def test_existing_command_route_remains_present():
    from wsgi import application

    routes = {str(rule) for rule in application.url_map.iter_rules()}

    assert "/api/bos/command" in routes
    assert "/admin/automation/command-center" in routes
    assert "/dashboard/api/bos/control-center" in routes
