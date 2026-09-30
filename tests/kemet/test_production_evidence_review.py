import json
from pathlib import Path

from ops.production_evidence_review import load_capacity, process_hygiene


def test_capacity_evidence_is_explicitly_non_production():
    data = load_capacity()
    assert data["available"] is True
    assert data["production_claim"] is False
    assert data["limitations"]


def test_process_hygiene_has_no_capacity_workers():
    result = process_hygiene()
    assert result["ok"] is True, result


def test_review_output_schema_exists_after_execution():
    path = Path("runtime_logs/production_evidence_review.json")
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["schema"] == "kemet.production_evidence_review.v1"
    assert data["production_claim"] is False
    assert data["governance"]["execution_authority"] is False
    assert data["governance"]["mcp"] is False
