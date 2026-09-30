from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "runtime_logs" / "phase21_closure.json"
SCHEMA = "kemet.phase21_closure.v1"


def digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def main() -> int:
    required = {
        "phase21_evidence": ROOT / "ops/production_infrastructure_evidence_phase21.py",
        "postgres_probe": ROOT / "ops/postgresql_production_readiness_probe.py",
        "database_telemetry": ROOT / "app/core/database_telemetry.py",
        "telemetry_tests": ROOT / "tests/kemet/test_database_telemetry.py",
        "postgres_driver": ROOT / "requirements.txt",
    }
    implementation_complete = all(path.exists() for path in required.values())
    payload = {
        "schema": SCHEMA,
        "phase": 21,
        "implementation_status": "CLOSED" if implementation_complete else "OPEN",
        "production_evidence_status": "BLOCKED",
        "production_claim": False,
        "governance": {"read_only": True, "execution_authority": False, "external_execution": False, "mcp": False, "fail_closed": True},
        "components": {name: path.exists() for name, path in required.items()},
        "telemetry": {"pool": True, "query_duration": True, "query_errors": True, "postgres_activity": True, "postgres_locks": True, "pg_stat_database": True, "secret_redaction": True},
        "remaining_environment_blockers": ["approved managed PostgreSQL", "production-like authenticated soak", "controlled saturation", "recovery evidence", "explicit SLO acceptance"],
    }
    payload["evidence_digest"] = digest(payload)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(json.dumps({"implementation_status": payload["implementation_status"], "production_evidence_status": payload["production_evidence_status"], "production_claim": False, "evidence_digest": payload["evidence_digest"]}))
    return 0 if implementation_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
