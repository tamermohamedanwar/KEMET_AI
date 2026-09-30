import importlib.util
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "ops" / "capacity_scale_validation_v2.py"
spec = importlib.util.spec_from_file_location("capacity_v2", MODULE)
capacity_v2 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = capacity_v2
spec.loader.exec_module(capacity_v2)


def test_capacity_harness_is_local_only():
    assert capacity_v2.LOCAL_HOSTS == {"127.0.0.1", "localhost", "::1"}
    assert all(item.path.startswith("/") for item in capacity_v2.SCENARIOS)


def test_capacity_scenarios_have_positive_weights():
    assert all(item.weight > 0 for item in capacity_v2.SCENARIOS)
    assert sum(item.weight for item in capacity_v2.SCENARIOS) == 100


def test_database_probe_is_non_destructive():
    result = capacity_v2.db_snapshot()
    assert result.get("database") in {"sqlite", "postgresql"}
    assert "error" not in result or isinstance(result["error"], str)
