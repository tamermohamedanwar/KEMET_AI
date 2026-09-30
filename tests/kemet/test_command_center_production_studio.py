from pathlib import Path


def test_command_center_exposes_production_studio_planning():
    route = Path("app/routes/command_center.py").read_text()
    assert "/api/bos/production-studio" in route
    assert "/api/bos/production-studio/plan" in route
    assert "production_studio_service" in route
