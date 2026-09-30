#!/usr/bin/env python3
"""Local-only capacity harness with optional synthetic authenticated journeys."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import re
import statistics
import subprocess
import threading
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
CSRF_RE = re.compile(r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)', re.I)


@dataclass(frozen=True)
class Scenario:
    name: str
    path: str
    weight: int


SCENARIOS = (
    Scenario("readiness", "/api/ready", 10),
    Scenario("workforce", "/api/workforce", 20),
    Scenario("corporate_force", "/api/workforce/corporate-force-v4", 20),
    Scenario("public_catalog", "/api/bos/public-api-catalog", 15),
    Scenario("revenue_center", "/api/bos/revenue-center", 15),
    Scenario("visibility", "/api/bos/visibility-intelligence?market=global", 10),
    Scenario("social_catalog", "/api/bos/social-channel-catalog", 10),
)


def resource_snapshot():
    try:
        out = subprocess.check_output(["ps", "-A", "-o", "pid=,pcpu=,rss=,args="], text=True, timeout=2)
    except Exception:
        return {"cpu_percent_sum": None, "rss_mb_sum": None}
    cpu = 0.0
    rss = 0
    for line in out.splitlines():
        if "gunicorn" not in line.lower():
            continue
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        try:
            cpu += float(parts[1])
            rss += int(parts[2])
        except ValueError:
            continue
    return {"cpu_percent_sum": round(cpu, 2), "rss_mb_sum": round(rss / 1024, 2)}


def db_snapshot():
    db_url = os.getenv("KEMET_CAPACITY_DB_URL", "")
    if db_url and db_url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=0)
            started = time.perf_counter()
            with engine.connect() as con:
                con.execute(text("SELECT 1"))
            latency = (time.perf_counter() - started) * 1000
            engine.dispose()
            return {"database": "postgresql", "probe_ms": round(latency, 3)}
        except Exception as exc:
            return {"database": "postgresql", "probe_ms": None, "error": type(exc).__name__}
    path = os.getenv("KEMET_SQLITE_PATH", "instance/supportai.db")
    if not os.path.exists(path):
        return {"database": "sqlite", "probe_ms": None, "available": False}
    try:
        import sqlite3
        started = time.perf_counter()
        con = sqlite3.connect(path, timeout=2)
        con.execute("PRAGMA busy_timeout=2000")
        con.execute("SELECT 1")
        latency = (time.perf_counter() - started) * 1000
        con.close()
        return {"database": "sqlite", "probe_ms": round(latency, 3), "available": True}
    except Exception as exc:
        return {"database": "sqlite", "probe_ms": None, "error": type(exc).__name__}


def authenticate(session: requests.Session, base_url: str, email: str, password: str, timeout: float):
    login_url = urljoin(base_url, "/login")
    page = session.get(login_url, timeout=timeout, allow_redirects=False)
    token_match = CSRF_RE.search(page.text)
    payload = {"email": email, "password": password}
    if token_match:
        payload["csrf_token"] = token_match.group(1)
    response = session.post(login_url, data=payload, timeout=timeout, allow_redirects=False)
    return response.status_code in {302, 303} and "/login" not in response.headers.get("Location", "")


def choose_scenario(rng: random.Random):
    return rng.choices(SCENARIOS, weights=[item.weight for item in SCENARIOS], k=1)[0]


def request_once(session, base_url, scenario, timeout):
    started = time.perf_counter()
    try:
        response = session.get(urljoin(base_url, scenario.path), timeout=timeout, allow_redirects=False)
        return scenario.name, response.status_code, (time.perf_counter() - started) * 1000
    except Exception:
        return scenario.name, 0, (time.perf_counter() - started) * 1000


def run_level(base_url, concurrency, duration, timeout, think_ms, authenticated, email, password, seed):
    stop_at = time.monotonic() + duration
    latencies = []
    statuses = {}
    scenarios = {}
    auth_failures = 0
    lock = threading.Lock()

    def worker(worker_id):
        nonlocal auth_failures
        rng = random.Random(seed + worker_id)
        session = requests.Session()
        if authenticated and not authenticate(session, base_url, email, password, timeout):
            with lock:
                auth_failures += 1
            return
        local_latencies = []
        local_statuses = {}
        local_scenarios = {}
        while time.monotonic() < stop_at:
            scenario = choose_scenario(rng)
            name, status, latency = request_once(session, base_url, scenario, timeout)
            local_latencies.append(latency)
            local_statuses[status] = local_statuses.get(status, 0) + 1
            local_scenarios[name] = local_scenarios.get(name, 0) + 1
            if think_ms:
                time.sleep(think_ms / 1000)
        with lock:
            latencies.extend(local_latencies)
            for key, value in local_statuses.items():
                statuses[key] = statuses.get(key, 0) + value
            for key, value in local_scenarios.items():
                scenarios[key] = scenarios.get(key, 0) + value
        session.close()

    samples = []
    sampling = True

    def sampler():
        while sampling:
            samples.append({"t": time.time(), "resource": resource_snapshot(), "db": db_snapshot()})
            time.sleep(0.5)

    sampler_thread = threading.Thread(target=sampler, daemon=True)
    sampler_thread.start()
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker, index) for index in range(concurrency)]
        for future in futures:
            future.result()
    elapsed = time.perf_counter() - started
    sampling = False
    sampler_thread.join(timeout=1)
    total = len(latencies)
    errors = sum(value for status, value in statuses.items() if status < 200 or status >= 400)
    cpus = [item["resource"]["cpu_percent_sum"] for item in samples if item["resource"]["cpu_percent_sum"] is not None]
    ram = [item["resource"]["rss_mb_sum"] for item in samples if item["resource"]["rss_mb_sum"] is not None]
    db = [item["db"]["probe_ms"] for item in samples if item["db"].get("probe_ms") is not None]
    return {
        "concurrency": concurrency, "duration_s": round(elapsed, 3), "think_ms": think_ms,
        "authenticated": authenticated, "requests": total, "rps": round(total / elapsed, 2) if elapsed else None,
        "p50_ms": round(pct(latencies, 50), 2) if latencies else None,
        "p95_ms": round(pct(latencies, 95), 2) if latencies else None,
        "p99_ms": round(pct(latencies, 99), 2) if latencies else None,
        "max_ms": round(max(latencies), 2) if latencies else None,
        "error_rate_percent": round(errors * 100 / total, 3) if total else 100.0,
        "status_counts": statuses, "scenario_counts": scenarios, "auth_failures": auth_failures,
        "cpu_percent_max": round(max(cpus), 2) if cpus else None, "cpu_percent_avg": round(statistics.mean(cpus), 2) if cpus else None,
        "ram_mb_max": round(max(ram), 2) if ram else None, "ram_mb_avg": round(statistics.mean(ram), 2) if ram else None,
        "db_probe_ms_max": round(max(db), 3) if db else None, "db_probe_ms_avg": round(statistics.mean(db), 3) if db else None,
        "samples": len(samples),
    }


def pct(values, percentile):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((percentile / 100) * (len(ordered) - 1)))))
    return ordered[index]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--duration", type=float, default=8)
    parser.add_argument("--levels", default="1,5,10,20,30")
    parser.add_argument("--think-ms", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=12)
    parser.add_argument("--profile", default="journey-ramp")
    parser.add_argument("--output", default="runtime_logs/capacity_scale_validation_v2.json")
    parser.add_argument("--authenticated", action="store_true")
    parser.add_argument("--email-env", default="KEMET_LOAD_TEST_EMAIL")
    parser.add_argument("--password-env", default="KEMET_LOAD_TEST_PASSWORD")
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if parsed.hostname not in LOCAL_HOSTS:
        raise SystemExit("Refusing non-local load target")
    if args.authenticated:
        email = os.getenv(args.email_env, "")
        password = os.getenv(args.password_env, "")
        if not email or not password:
            raise SystemExit("Authenticated mode requires synthetic credentials in environment")
    else:
        email = password = ""
    levels = [int(value) for value in args.levels.split(",") if value.strip()]
    results = []
    for level in levels:
        result = run_level(args.url, level, args.duration, args.timeout, args.think_ms, args.authenticated, email, password, 20260916)
        results.append(result)
        print(json.dumps(result, sort_keys=True))
    payload = {
        "schema": "kemet.capacity_scale_validation.v2",
        "profile": args.profile,
        "target": args.url,
        "local_only": True,
        "authenticated": args.authenticated,
        "synthetic_credentials_only": args.authenticated,
        "levels": levels,
        "scenario_weights": {item.name: item.weight for item in SCENARIOS},
        "results": results,
        "safety": {
            "external_side_effects": False,
            "external_provider_calls": False,
            "publication": False,
            "payment": False,
            "messaging": False,
            "commerce_execution": False,
        },
        "limitations": [
            "Concurrent workers are not equivalent to concurrent human users.",
            "Authenticated mode requires a dedicated synthetic test identity and tenant.",
            "SQLite is diagnostic only; PostgreSQL/managed DB remains required for production capacity certification.",
            "This harness does not execute approval, publication, payment, messaging or commerce actions.",
        ],
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(json.dumps({"saved": args.output, "profile": args.profile}, sort_keys=True))


if __name__ == "__main__":
    main()
