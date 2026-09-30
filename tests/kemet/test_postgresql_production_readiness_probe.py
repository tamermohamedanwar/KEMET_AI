import json
from pathlib import Path

from ops.postgresql_production_readiness_probe import OUTPUT, digest, probe


def test_probe_is_fail_closed_without_postgresql():
    data = probe()
    if not data["postgresql_detected"]:
        assert data["status"] == "BLOCKED"
        assert data["connection_attempted"] is False
        assert data["production_claim"] is False


def test_probe_never_exposes_secret():
    data = probe()
    assert data["secret_exposed"] is False
    assert "url" not in data
    assert "password" not in data


def test_probe_output_schema_exists():
    data = json.loads(OUTPUT.read_text())
    assert data["schema"] == "kemet.postgresql_production_readiness_probe.v1"
    assert data["read_only"] is True
    assert data["production_claim"] is False


def test_probe_digest_is_reproducible():
    data = json.loads(OUTPUT.read_text())
    expected = data.pop("evidence_digest")
    assert expected == digest(data)
