import json
from pathlib import Path

from ops.phase21_closure import OUTPUT, digest, main


def test_phase21_closure_is_implementation_closed_but_production_blocked():
    assert main() == 0
    data = json.loads(OUTPUT.read_text())
    assert data["schema"] == "kemet.phase21_closure.v1"
    assert data["implementation_status"] == "CLOSED"
    assert data["production_evidence_status"] == "BLOCKED"
    assert data["production_claim"] is False
    assert data["governance"]["mcp"] is False


def test_phase21_closure_digest_is_reproducible():
    data = json.loads(OUTPUT.read_text())
    expected = data.pop("evidence_digest")
    assert expected == digest(data)
