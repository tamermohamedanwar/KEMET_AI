#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "runtime_logs" / "production_infrastructure_evidence_phase21.json"
CAPACITY = ROOT / "runtime_logs" / "capacity_authenticated_matrix_phase15_hardened.json"
SCHEMA = "kemet.production_infrastructure_evidence.v1"


def endpoint(url: str) -> dict:
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=5, allow_redirects=False)
        return {
            "ok": response.status_code < 500,
            "status": response.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except requests.RequestException as exc:
        return {"ok": False, "status": None, "error": type(exc).__name__}


def process_snapshot() -> dict:
    try:
        output = subprocess.check_output(["ps", "-A", "-o", "pid=,args="], text=True, timeout=3)
    except Exception as exc:
        return {"available": False, "error": type(exc).__name__}
    rows = [line.strip() for line in output.splitlines() if line.strip()]
    current_pid = str(os.getpid())
    parent_pid = str(os.getppid())
    def is_real_worker(line):
        parts = line.split(None, 1)
        if not parts or parts[0] in {current_pid, parent_pid}: return False
        command = parts[1].lower() if len(parts) > 1 else ""
        if "sh -c" in command or "bash -c" in command or "python3 -c" in command: return False
        return True
    capacity = [line for line in rows if "capacity_authenticated_matrix" in line.lower() and is_real_worker(line)]
    pytest = [line for line in rows if ".venv/bin/python -m pytest" in line and is_real_worker(line)]
    return {
        "available": True,
        "unexpected_capacity_processes": capacity,
        "unexpected_pytest_processes": pytest,
        "ok": not capacity and not pytest,
    }


def database_evidence() -> dict:
    raw = os.getenv("KEMET_CAPACITY_DB_URL") or os.getenv("DATABASE_URL") or ""
    scheme = urlparse(raw).scheme.lower() if raw else ""
    postgres = scheme.startswith("postgres")
    return {
        "configured": bool(raw),
        "engine": "postgresql" if postgres else (scheme or "sqlite_or_default"),
        "managed_postgresql": False,
        "postgres_connection_string_present": postgres,
        "secret_value_exposed": False,
        "pool_query_lock_telemetry": False,
    }


def capacity_evidence() -> dict:
    if not CAPACITY.exists():
        return {"available": False, "production_claim": False}
    try:
        data = json.loads(CAPACITY.read_text())
    except Exception as exc:
        return {"available": False, "production_claim": False, "error": type(exc).__name__}
    return {
        "available": True,
        "production_claim": bool(data.get("production_claim")),
        "environment": "Termux/Android SQLite clone",
        "production_like": False,
        "soak": data.get("soak") or {},
        "limitations": data.get("limitations") or [],
    }


def evidence_matrix() -> dict:
    return {
        "managed_postgresql": {"required": True, "state": "BLOCKED", "proof": "managed PostgreSQL evidence is unavailable"},
        "db_pool_query_lock_telemetry": {"required": True, "state": "BLOCKED", "proof": "pool/query/lock telemetry is unavailable"},
        "production_like_soak": {"required": True, "state": "BLOCKED", "proof": "current soak uses Termux/Android SQLite clone"},
        "saturation_test": {"required": True, "state": "BLOCKED", "proof": "approved production-like saturation environment unavailable"},
        "recovery_after_saturation": {"required": True, "state": "BLOCKED", "proof": "recovery evidence is unavailable"},
        "explicit_slo_acceptance": {"required": True, "state": "BLOCKED", "proof": "no production SLO acceptance artifact is present"},
    }


def slo_contract() -> dict:
    metrics = [
        "availability", "error_rate", "p50_latency", "p95_latency", "p99_latency",
        "db_latency", "db_pool_health", "approval_to_execution_latency",
        "evidence_integrity", "workforce_reliability",
    ]
    return {
        "status": "PENDING_ACCEPTANCE",
        "acceptance_owner": None,
        "targets_production_approved": False,
        "metrics": metrics,
        "policy": "Targets require explicit owner acceptance and supporting production-like evidence before readiness review.",
    }


def canonical_digest(report: dict) -> str:
    payload = dict(report)
    payload.pop("evidence_digest", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    matrix = evidence_matrix()
    db = database_evidence()
    capacity = capacity_evidence()
    runtime = {
        "root": endpoint("http://127.0.0.1:5000/"),
        "login": endpoint("http://127.0.0.1:5000/login"),
        "bridge": endpoint("http://127.0.0.1:8770/health"),
    }
    report = {
        "schema": SCHEMA,
        "timestamp": now,
        "environment": {
            "local": True,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "project_root": str(ROOT),
            "production_claim": False,
        },
        "database": db,
        "runtime": runtime,
        "process_hygiene": process_snapshot(),
        "capacity": capacity,
        "evidence_matrix": matrix,
        "slo_contract": slo_contract(),
        "observability": {
            "correlation_fields": [
                "trace_id", "span_id", "tenant_id", "organization_id", "assignment_id",
                "task_id", "approval_id", "execution_id", "evidence_id", "outcome_id",
            ],
            "decision_chain": ["Decision", "Approval", "Execution", "Evidence", "Outcome", "Learning"],
            "semantic_convention_alignment": "OpenTelemetry",
            "logging_protection_alignment": "OWASP",
            "measurement_to_management_alignment": "NIST AI RMF",
        },
        "provenance": {
            "source_artifacts": [
                "runtime_logs/production_evidence_review.json",
                "runtime_logs/capacity_authenticated_matrix_phase15_hardened.json",
            ],
            "scope": "read_only production infrastructure evidence review",
            "redaction": True,
        },
        "governance": {
            "read_only": True,
            "execution_authority": False,
            "external_execution": False,
            "human_approval_required": True,
            "mcp": False,
            "fail_closed": True,
        },
        "status": "BLOCKED",
        "production_claim": False,
        "limitations": [
            "Managed PostgreSQL evidence is unavailable.",
            "DB pool/query/lock telemetry is unavailable.",
            "Current capacity evidence uses a Termux/Android SQLite clone and is non-production.",
            "Production-like soak and controlled saturation evidence are unavailable.",
            "Recovery-after-saturation evidence is unavailable.",
            "Explicit production SLO acceptance is unavailable.",
        ],
    }
    report["missing_evidence"] = [name for name, item in matrix.items() if item["state"] == "BLOCKED"]
    report["evidence_digest"] = canonical_digest(report)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": report["status"],
        "production_claim": report["production_claim"],
        "missing_evidence": report["missing_evidence"],
        "evidence_digest": report["evidence_digest"],
        "output": str(OUTPUT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
