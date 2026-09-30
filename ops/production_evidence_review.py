#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "runtime_logs" / "production_evidence_review.json"
CAPACITY = ROOT / "runtime_logs" / "capacity_authenticated_matrix_phase15_hardened.json"
REQUIRED_EVIDENCE = ("managed_postgresql", "db_pool_query_lock_telemetry", "production_like_soak", "recovery_after_saturation", "explicit_slo_acceptance")


def endpoint(url: str) -> dict:
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=5, allow_redirects=False)
        return {"ok": response.status_code < 500, "status": response.status_code, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
    except requests.RequestException as exc:
        return {"ok": False, "status": None, "error": type(exc).__name__}


def process_hygiene() -> dict:
    try:
        output = subprocess.check_output(["ps", "-A", "-o", "args="], text=True, timeout=3)
    except Exception:
        return {"ok": False, "reason": "process_snapshot_unavailable"}
    capacity_processes = [line.strip() for line in output.splitlines() if "capacity_authenticated_matrix" in line.lower()]
    return {"ok": not capacity_processes, "unexpected_capacity_processes": capacity_processes}


def pytest_hygiene() -> dict:
    try:
        output = subprocess.check_output(["ps", "-A", "-o", "args="], text=True, timeout=3)
    except Exception:
        return {"ok": False, "reason": "process_snapshot_unavailable"}
    pytest_processes = [line.strip() for line in output.splitlines() if ".venv/bin/python -m pytest" in line]
    return {"ok": not pytest_processes, "unexpected_pytest_processes": pytest_processes}


def load_capacity() -> dict:
    if not CAPACITY.exists():
        return {"available": False}
    try:
        data = json.loads(CAPACITY.read_text())
        return {"available": True, "production_claim": bool(data.get("production_claim")), "soak": data.get("soak") or {}, "limitations": data.get("limitations", [])}
    except Exception as exc:
        return {"available": False, "error": type(exc).__name__}


def main() -> int:
    db_url = os.getenv("KEMET_CAPACITY_DB_URL") or os.getenv("DATABASE_URL") or ""
    scheme = urlparse(db_url).scheme.lower() if db_url else ""
    postgres = scheme.startswith("postgres")
    evidence = {key: False for key in REQUIRED_EVIDENCE}
    report = {
        "schema": "kemet.production_evidence_review.v1", "scope": "production_operations_evidence_review",
        "local_environment": True, "production_claim": False,
        "database": {"configured": bool(db_url), "scheme": scheme or None, "managed_postgresql_evidence": postgres},
        "runtime": {"root": endpoint("http://127.0.0.1:5000/"), "login": endpoint("http://127.0.0.1:5000/login"), "bridge": endpoint("http://127.0.0.1:8770/health")},
        "process_hygiene": process_hygiene(), "capacity": load_capacity(), "required_evidence": evidence,
        "missing_evidence": list(REQUIRED_EVIDENCE), "status": "BLOCKED",
        "governance": {"read_only": True, "execution_authority": False, "external_execution": False, "human_approval_required": True, "mcp": False, "fail_closed": True},
        "basis": {"opentelemetry": "semantic-convention-aligned correlation and metric naming", "owasp": "protected, attributable application/security logging", "nist_ai_rmf": "measure evidence informs manage decision"},
    }
    report["status"] = "READY_FOR_GATE" if all(evidence.values()) else "BLOCKED"
    report["missing_evidence"] = [key for key, value in evidence.items() if not value]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "missing_evidence": report["missing_evidence"], "output": str(OUTPUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
