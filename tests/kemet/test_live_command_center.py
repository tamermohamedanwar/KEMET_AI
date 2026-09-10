import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_command_center_has_live_context():
    from wsgi import application

    with application.app_context():
        from app.core.orchestration.command_center_wiring import (
            KemetCommandCenterWiring,
        )

        wiring = KemetCommandCenterWiring()
        context = wiring.live_context(1)

        assert isinstance(context, dict)
        assert context["organization_id"] == 1
        assert "organization_name" in context
        assert "revenue" in context
        assert "leads" in context
        assert "customers" in context
        assert "open_tickets" in context
        assert "automation_executions" in context


def test_live_context_is_read_only():
    from wsgi import application

    with application.app_context():
        from app.core.orchestration.command_center_wiring import (
            KemetCommandCenterWiring,
        )

        wiring = KemetCommandCenterWiring()

        before = wiring.live_context(1)
        after = wiring.live_context(1)

        assert before == after


def test_live_context_global_and_tenant_are_separate():
    from wsgi import application

    with application.app_context():
        from app.core.orchestration.command_center_wiring import (
            KemetCommandCenterWiring,
        )

        wiring = KemetCommandCenterWiring()

        global_context = wiring.live_context()
        tenant_context = wiring.live_context(1)

        assert global_context["organization_id"] is None
        assert tenant_context["organization_id"] == 1

        assert global_context["users"] >= tenant_context["users"]
        assert global_context["revenue"] >= tenant_context["revenue"]


def test_existing_wiring_api_still_works():
    from wsgi import application

    with application.app_context():
        from app.core.orchestration.command_center_wiring import (
            KemetCommandCenterWiring,
        )

        wiring = KemetCommandCenterWiring()

        # Inspect the real public API instead of assuming a signature.
        assert hasattr(wiring, "run")
        assert callable(wiring.run)


def test_live_context_contains_governance_safe_metadata():
    from wsgi import application

    with application.app_context():
        from app.core.orchestration.command_center_wiring import (
            KemetCommandCenterWiring,
        )

        wiring = KemetCommandCenterWiring()

        context = wiring.live_context(1)

        assert context["organization_id"] == 1

        # LiveBusinessData is read-only; it must not expose
        # execution permission as an enabled state.
        assert "external_execution" not in context or context["external_execution"] is False
