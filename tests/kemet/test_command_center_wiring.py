import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))

from app.core.orchestration.command_center_wiring import KemetCommandCenterWiring


def test_command_center_wiring_analysis():
    service = KemetCommandCenterWiring()

    result = service.analyze(
        revenue_data={
            "leads": 100,
            "opportunities": 20,
            "customers": 5,
            "revenue": 50000,
            "pipeline_value": 150000,
        },
        sales_data={
            "leads": 100,
            "qualified_leads": 60,
            "opportunities": 20,
            "customers": 5,
            "pipeline_value": 150000,
        },
        customer_data={
            "customer_id": "command-center-demo",
            "channel": "web",
            "message": "Command Center wiring test",
        },
        analytics_data={
            "revenue": 50000,
            "cost": 10000,
            "customers": 5,
            "leads": 100,
            "automated_tasks": 40,
            "manual_hours_saved": 20,
        },
    )

    assert result["ok"] is True
    assert result["mode"] == "advisory"
    assert result["external_execution"] is False
    assert result["database_mutation"] is False

    analysis = result["analysis"]

    for key in (
        "intelligence",
        "revenue",
        "sales",
        "customer",
        "analytics",
    ):
        assert key in analysis


def test_command_center_wiring_run():
    service = KemetCommandCenterWiring()

    result = service.run(
        revenue_data={"revenue": 100000, "pipeline_value": 200000},
        sales_data={"leads": 50, "customers": 5},
    )

    assert result["ok"] is True
    assert result["status"] == "waiting_approval"
    assert result["approval_required"] is True
    assert result["external_execution"] is False
    assert result["database_mutation"] is False


def test_command_center_wiring_status():
    result = KemetCommandCenterWiring().status()

    assert result["ok"] is True
    assert result["activation_layer"] == "active"
    assert result["approval_required"] is True
    assert result["external_execution"] is False
    assert result["database_mutation"] is False
