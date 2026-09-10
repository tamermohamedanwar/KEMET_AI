from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_command_center_template_exists():
    path = ROOT / "app" / "templates" / "admin" / "command_center.html"
    assert path.exists()
    assert path.stat().st_size > 0


def test_command_center_route_exists():
    path = ROOT / "app" / "routes" / "bos_command_center.py"
    text = path.read_text(encoding="utf-8")
    assert "/admin/automation/command-center" in text


def test_command_api_exists():
    path = ROOT / "app" / "routes" / "bos_command.py"
    text = path.read_text(encoding="utf-8")
    assert "/command" in text


def test_existing_bos_intelligence_exists():
    path = ROOT / "app" / "services" / "bos_intelligence.py"
    assert path.exists()


def test_existing_orchestrator_exists():
    path = ROOT / "app" / "automation" / "orchestrator.py"
    assert path.exists()
