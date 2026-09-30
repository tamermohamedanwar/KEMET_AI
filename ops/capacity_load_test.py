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


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((p / 100) * (len(ordered) - 1)))))
    return ordered[index]


def process_snapshot():
    try:
        out = subprocess.check_output(
            ["ps", "-A", "-o", "pid=,pcpu=,rss=,args="], text=True, timeout=2
        )
    except Exception:
        return {"cpu_percent_sum": None, "rss_mb_sum": None, "processes": []}
    rows = []
    cpu = 0.0
    rss_kb = 0
    for line in out.splitlines():
        if "gunicorn" not in line.lower():
            continue
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        try:
            pid = int(parts[0])
            pcpu = float(parts[1])
            rss = int(parts[2])
        except ValueError:
            continue
        cpu += pcpu
        rss_kb += rss
        rows.append({"pid": pid, "cpu_percent": pcpu, "rss_kb": rss})
    return {"cpu_percent_sum": round(cpu, 2), "rss_mb_sum": round(rss_kb / 1024, 2), "processes": rows}


def request_once(url, timeout):
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=timeout, allow_redirects=False)
        elapsed = (time.perf_counter() - started) * 1000
        return response.status_code, elapsed
    except Exception:
        elapsed = (time.perf_counter() - started) * 1000
        return 0, elapsed


def run_level(url, concurrency, duration, timeout):
    stop_at = time.monotonic() + duration
    latencies = []
    status_counts = {}
    lock = threading.Lock()

    def worker():
        local_latencies = []
        local_status = {}
        while time.monotonic() < stop_at:
            status, latency = request_once(url, timeout)
            local_latencies.append(latency)
            local_status[status] = local_status.get(status, 0) + 1
        with lock:
            latencies.extend(local_latencies)
            for key, value in local_status.items():
                status_counts[key] = status_counts.get(key, 0) + value

    before = process_snapshot()
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker) for _ in range(concurrency)]
        for future in futures:
            future.result()
    elapsed = time.perf_counter() - started
    after = process_snapshot()
    total = len(latencies)
    errors = sum(count for status, count in status_counts.items() if status < 200 or status >= 400)
    return {
        "concurrency": concurrency,
        "duration_s": round(elapsed, 3),
        "requests": total,
        "requests_per_sec": round(total / elapsed, 2) if elapsed else None,
        "p50_ms": round(percentile(latencies, 50), 2) if latencies else None,
        "p95_ms": round(percentile(latencies, 95), 2) if latencies else None,
        "p99_ms": round(percentile(latencies, 99), 2) if latencies else None,
        "max_ms": round(max(latencies), 2) if latencies else None,
        "error_rate_percent": round((errors / total) * 100, 3) if total else 100.0,
        "status_counts": status_counts,
        "process_before": before,
        "process_after": after,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5000/api/ready")
    parser.add_argument("--duration", type=float, default=8)
    parser.add_argument("--levels", default="1,5,10,20,40")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--output", default="runtime_logs/capacity_load_results.json")
    args = parser.parse_args()

    parsed = urlparse(args.url)
    if parsed.hostname not in LOCAL_HOSTS:
        raise SystemExit("Refusing non-local load target")
    levels = [int(item) for item in args.levels.split(",") if item.strip()]
    results = []
    for level in levels:
        result = run_level(args.url, level, args.duration, args.timeout)
        results.append(result)
        print(json.dumps(result, sort_keys=True))

    payload = {
        "schema": "kemet.capacity_load_test.v1",
        "target": args.url,
        "local_only": True,
        "duration_per_level_s": args.duration,
        "levels": levels,
        "results": results,
        "db_utilization": "not directly measurable from the current SQLite runtime; readiness endpoint pressure is included as an application-level proxy",
        "notes": [
            "This is a localhost capacity probe, not a production/public stress test.",
            "Concurrent users are represented by concurrent request workers; no think-time model is applied.",
            "Sustainable capacity requires a real user journey and external dependency load profile before production claims."
        ],
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(json.dumps({"saved": args.output, "levels": levels}, sort_keys=True))


if __name__ == "__main__":
    main()
