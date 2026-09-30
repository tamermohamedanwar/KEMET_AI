from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.core.database_telemetry import database_telemetry
from app.services.reliability_slo import reliability_slo

SCHEMA = "kemet.observability_health.v1"
OUTPUT = Path("runtime_logs/observability_health.json")


def _digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_report() -> dict[str, Any]:
    app = create_app()
    with app.app_context():
        db = database_telemetry.snapshot()
    production = os.getenv("FLASK_ENV", "development").strip().lower() == "production"
    postgres = db.get("postgresql", {})
    checks = {
        "database_telemetry": bool(db.get("read_only")) and db.get("secret_exposed") is False,
        "postgresql_evidence": bool(postgres.get("connection_ok")) if postgres.get("available") else False,
        "reliability_catalog": reliability_slo.catalog().get("measurement_only") is True,
    }
    status = "HEALTHY" if all(checks.values()) else "DEGRADED"
    if not production and not checks["postgresql_evidence"]:
        status = "LOCAL_OBSERVABILITY_VERIFIED"
    report = {
        "schema": SCHEMA,
        "version": "1.0",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "environment": os.getenv("FLASK_ENV", "development"),
        "status": status,
        "checks": checks,
        "database": db,
        "reliability": reliability_slo.catalog(),
        "secret_exposed": False,
        "production_claim": False,
    }
    digest_input = dict(report)
    digest_input.pop("observed_at", None)
    report["evidence_digest"] = _digest(digest_input)
    return report


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    report = build_report()
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
