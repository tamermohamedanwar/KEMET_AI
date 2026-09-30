#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

OUTPUT = Path("runtime_logs/postgresql_production_readiness_probe.json")
SCHEMA = "kemet.postgresql_production_readiness_probe.v1"


def probe() -> dict:
    raw = os.getenv("KEMET_CAPACITY_DB_URL") or os.getenv("DATABASE_URL") or ""
    parsed = urlparse(raw) if raw else None
    report = {
        "schema": SCHEMA,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configured": bool(raw),
        "scheme": parsed.scheme if parsed else None,
        "postgresql_detected": bool(parsed and parsed.scheme.startswith("postgres")),
        "connection_attempted": False,
        "connection_ok": False,
        "read_only": True,
        "secret_exposed": False,
        "checks": {},
        "status": "BLOCKED",
        "production_claim": False,
    }
    if not report["postgresql_detected"]:
        report["checks"] = {
            "server_version": "NOT_EXECUTED",
            "max_connections": "NOT_EXECUTED",
            "active_connections": "NOT_EXECUTED",
            "locks": "NOT_EXECUTED",
            "query_statistics": "NOT_EXECUTED",
        }
        return report
    try:
        import psycopg
    except ImportError:
        report["checks"] = {"driver": "NOT_INSTALLED"}
        return report
    report["connection_attempted"] = True
    try:
        with psycopg.connect(raw, connect_timeout=5, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
                cur.execute("SHOW max_connections")
                max_connections = int(cur.fetchone()[0])
                cur.execute("SELECT count(*) FROM pg_stat_activity")
                active = int(cur.fetchone()[0])
                cur.execute("SELECT count(*) FROM pg_locks WHERE NOT granted")
                waiting_locks = int(cur.fetchone()[0])
                cur.execute("SELECT current_setting('track_activities')")
                track_activities = cur.fetchone()[0]
            report["connection_ok"] = True
            report["checks"] = {
                "server_version_major": str(version).split()[1].split('.')[0],
                "max_connections": max_connections,
                "active_connections": active,
                "waiting_locks": waiting_locks,
                "track_activities": track_activities,
                "pg_stat_activity": "AVAILABLE",
                "pg_locks": "AVAILABLE",
            }
    except Exception as exc:
        report["checks"] = {"connection_error": type(exc).__name__}
    return report


def digest(report: dict) -> str:
    payload = dict(report)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


if __name__ == "__main__":
    result = probe()
    result["evidence_digest"] = digest(result)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "configured", "postgresql_detected", "connection_attempted", "connection_ok", "secret_exposed", "evidence_digest")}))
