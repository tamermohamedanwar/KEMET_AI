#!/usr/bin/env python3
import argparse
import concurrent.futures
import json
import os
import statistics
import subprocess
import threading
import time
from urllib.parse import urlparse

import requests

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def pct(values, p):
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, max(0, int(round((p / 100) * (len(values) - 1)))))
    return values[idx]


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
    db_path = os.getenv("KEMET_SQLITE_PATH", "instance/supportai.db")
    if not os.path.exists(db_path):
        return {"sqlite": False, "path": db_path}
    try:
        import sqlite3
        started = time.perf_counter()
        con = sqlite3.connect(db_path, timeout=2)
        con.execute("PRAGMA busy_timeout=2000")
        con.execute("SELECT 1")
        latency = (time.perf_counter() - started) * 1000
        con.close()
        return {"sqlite": True, "path": db_path, "probe_ms": round(latency, 3)}
    except Exception as exc:
        return {"sqlite": True, "path": db_path, "probe_ms": None, "error": type(exc).__name__}


def request_once(url, timeout):
    started = time.perf_counter()
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=False)
        return r.status_code, (time.perf_counter() - started) * 1000
    except Exception:
        return 0, (time.perf_counter() - started) * 1000


def run_level(url, concurrency, duration, timeout, think_ms):
    stop_at = time.monotonic() + duration
    latencies = []
    statuses = {}
    lock = threading.Lock()

    def worker():
        local_latencies = []
        local_statuses = {}
        while time.monotonic() < stop_at:
            status, latency = request_once(url, timeout)
            local_latencies.append(latency)
            local_statuses[status] = local_statuses.get(status, 0) + 1
            if think_ms:
                time.sleep(think_ms / 1000)
        with lock:
            latencies.extend(local_latencies)
            for status, count in local_statuses.items():
                statuses[status] = statuses.get(status, 0) + count

    samples = []
    sampling = True

    def sampler():
        while sampling:
            samples.append({"t": time.time(), "resource": resource_snapshot(), "db": db_snapshot()})
            time.sleep(0.5)

    sample_thread = threading.Thread(target=sampler, daemon=True)
    sample_thread.start()
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker) for _ in range(concurrency)]
        for future in futures:
            future.result()
    elapsed = time.perf_counter() - started
    sampling = False
    sample_thread.join(timeout=1)
    total = len(latencies)
    errors = sum(v for k, v in statuses.items() if k < 200 or k >= 400)
    cpus = [s["resource"]["cpu_percent_sum"] for s in samples if s["resource"]["cpu_percent_sum"] is not None]
    ram = [s["resource"]["rss_mb_sum"] for s in samples if s["resource"]["rss_mb_sum"] is not None]
    db = [s["db"]["probe_ms"] for s in samples if s["db"].get("probe_ms") is not None]
    return {
        "concurrency": concurrency,
        "duration_s": round(elapsed, 3),
        "think_ms": think_ms,
        "requests": total,
        "rps": round(total / elapsed, 2) if elapsed else None,
        "p50_ms": round(pct(latencies, 50), 2) if latencies else None,
        "p95_ms": round(pct(latencies, 95), 2) if latencies else None,
        "p99_ms": round(pct(latencies, 99), 2) if latencies else None,
        "max_ms": round(max(latencies), 2) if latencies else None,
        "error_rate_percent": round(errors * 100 / total, 3) if total else 100.0,
        "status_counts": statuses,
        "cpu_percent_max": round(max(cpus), 2) if cpus else None,
        "cpu_percent_avg": round(statistics.mean(cpus), 2) if cpus else None,
        "ram_mb_max": round(max(ram), 2) if ram else None,
        "ram_mb_avg": round(statistics.mean(ram), 2) if ram else None,
        "db_probe_ms_max": round(max(db), 3) if db else None,
        "db_probe_ms_avg": round(statistics.mean(db), 3) if db else None,
        "samples": len(samples),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:5000/api/ready")
    p.add_argument("--duration", type=float, default=8)
    p.add_argument("--levels", default="1,5,10,20,30,40")
    p.add_argument("--think-ms", type=int, default=0)
    p.add_argument("--timeout", type=float, default=12)
    p.add_argument("--profile", default="ramp")
    p.add_argument("--output", default="runtime_logs/capacity_scale_validation.json")
    args = p.parse_args()
    parsed = urlparse(args.url)
    if parsed.hostname not in LOCAL_HOSTS:
        raise SystemExit("Refusing non-local load target")
    levels = [int(x) for x in args.levels.split(",") if x.strip()]
    results = []
    for level in levels:
        result = run_level(args.url, level, args.duration, args.timeout, args.think_ms)
        results.append(result)
        print(json.dumps(result, sort_keys=True))
    payload = {
        "schema": "kemet.capacity_scale_validation.v1",
        "profile": args.profile,
        "target": args.url,
        "local_only": True,
        "levels": levels,
        "results": results,
        "limitations": [
            "Synthetic request workers are not equivalent to real human users.",
            "SQLite probe measures local query responsiveness, not production DB utilization.",
            "No external provider, connector, publication, payment, messaging or execution path is exercised.",
            "Production capacity requires a production-like PostgreSQL/managed DB and network topology."
        ]
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps({"saved": args.output, "profile": args.profile}, sort_keys=True))


if __name__ == "__main__":
    main()
