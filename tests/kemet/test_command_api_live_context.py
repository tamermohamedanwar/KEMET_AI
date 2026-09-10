import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_command_api_route_exists():
    from wsgi import application

    routes = {str(rule) for rule in application.url_map.iter_rules()}
    assert "/api/bos/command" in routes


def test_orchestrator_is_preserved():
    route = ROOT / "app/routes/bos_command.py"
    text = route.read_text()

    assert "orchestrator.execute(" in text
    assert "@login_required" in text


def test_live_context_is_built_and_returned():
    route = ROOT / "app/routes/bos_command.py"
    text = route.read_text()

    assert "KemetCommandCenterWiring" in text
    assert "build_command_context" in text
    assert "live_command_context" in text
    assert '"live_context": live_command_context' in text


def test_live_context_is_tenant_scoped():
    from wsgi import application

    with application.app_context():
        from app.core.orchestration.command_center_wiring import (
            KemetCommandCenterWiring,
        )

        service = KemetCommandCenterWiring()

        context = service.build_command_context(
            organization_id=1,
            user_id=1,
            message="Analyze current business performance",
        )

        assert context["organization_id"] == 1
        assert context["user_id"] == 1
        assert context["live_business"]["organization_id"] == 1


def test_governance_remains_locked():
    from wsgi import application

    with application.app_context():
        from app.core.orchestration.command_center_wiring import (
            KemetCommandCenterWiring,
        )

        service = KemetCommandCenterWiring()

        context = service.build_command_context(
            organization_id=1,
            user_id=1,
            message="Execute action",
        )

        assert context["mode"] == "advisory"
        assert context["approval_required"] is True
        assert context["external_execution"] is False
        assert context["database_mutation"] is False
