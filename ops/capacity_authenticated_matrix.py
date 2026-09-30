#!/usr/bin/env python3
import argparse
import concurrent.futures
import json
import os
import re
import shutil
import secrets
import signal
import statistics
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE_DB = ROOT / "instance" / "supportai.db"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, max(0, int(round((p / 100) * (len(values) - 1)))))
    return values[idx]


def ps_snapshot():
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
            pass
    return {"cpu_percent_sum": round(cpu, 2), "rss_mb_sum": round(rss / 1024, 2)}


def db_probe(db_path):
    import sqlite3
    started = time.perf_counter()
    try:
        con = sqlite3.connect(db_path, timeout=2)
        con.execute("PRAGMA busy_timeout=2000")
        con.execute("SELECT COUNT(*) FROM users")
        con.close()
        return round((time.perf_counter() - started) * 1000, 3)
    except Exception:
        return None


def seed_db(path, email, password):
    shutil.copy2(SOURCE_DB, path)
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    os.environ["SECRET_KEY"] = secrets.token_hex(32)
    os.environ["FLASK_ENV"] = "testing"
    from app import create_app, db
    from app.models.user import User
    from app.models.organization import Organization
    from app.models.subscription import Subscription
    from werkzeug.security import generate_password_hash
    from sqlalchemy import text
    app = create_app()
    with app.app_context():
        org = Organization(name="Kemet Capacity Synthetic", slug=f"capacity-{os.getpid()}")
        db.session.add(org)
        db.session.flush()
        db.session.add(Subscription(organization_id=org.id, plan="business", status="active"))
        db.session.add(User(organization_id=org.id, full_name="Kemet Capacity Synthetic", email=email, password_hash=generate_password_hash(password), role="admin"))
        for name, table, columns in (
            ("ix_capacity_exec", "automation_executions", "created_at, workflow_id, status"),
            ("ix_capacity_tickets", "tickets", "organization_id, created_at, status"),
            ("ix_capacity_replies", "ticket_replies", "created_at, ticket_id, is_ai, is_staff"),
            ("ix_capacity_leads", "demo_leads", "organization_id, created_at, status"),
            ("ix_capacity_payments", "payments", "organization_id, created_at, status"),
            ("ix_capacity_subscriptions", "subscriptions", "organization_id, status"),
            ("ix_capacity_usage", "ai_usage", "organization_id, created_at"),
        ):
            db.session.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"))
        db.session.commit()


def wait_ready(base, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = requests.get(urljoin(base, "/api/health"), timeout=2)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.25)
    return False


def login(session, base, email, password):
    page = session.get(urljoin(base, "/login"), timeout=5)
    token = re.search(r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)', page.text)
    data = {"email": email, "password": password}
    if token:
        data["csrf_token"] = token.group(1)
    response = session.post(urljoin(base, "/login"), data=data, timeout=8, allow_redirects=False)
    return response.status_code in (302, 303) and "Location" in response.headers

SCENARIOS = [
    ("dashboard", "/dashboard", 0.20),
    ("kpis", "/dashboard/api/kpis?period=30d", 0.55),
    ("settings", "/settings", 0.25),
]


def choose_scenario(n, rng):
    value = rng.random()
    total = 0.0
    for name, path, weight in SCENARIOS:
        total += weight
        if value <= total:
            return name, path
    return SCENARIOS[-1][0], SCENARIOS[-1][1]

def run_profile(base, concurrency, duration, think_ms, cookie_values, timeout, db_path):
    stop_at = time.monotonic() + duration
    latencies = []
    statuses = {}
    scenario_counts = {}
    errors = []
    lock = threading.Lock()

    def worker(index):
        import random
        session = requests.Session()
        session.cookies.update(cookie_values)
        rng = random.Random(index * 100003 + int(time.time()))
        local_latencies = []
        local_statuses = {}
        local_scenarios = {}
        while time.monotonic() < stop_at:
            name, path = choose_scenario(index, rng)
            started = time.perf_counter()
            try:
                response = session.get(urljoin(base, path), timeout=timeout, allow_redirects=False)
                latency = (time.perf_counter() - started) * 1000
                status = response.status_code
            except requests.RequestException as exc:
                latency = (time.perf_counter() - started) * 1000
                status = 0
                errors.append(type(exc).__name__)
            local_latencies.append(latency)
            local_statuses[status] = local_statuses.get(status, 0) + 1
            local_scenarios[name] = local_scenarios.get(name, 0) + 1
            if think_ms:
                time.sleep(think_ms / 1000)
        with lock:
            latencies.extend(local_latencies)
            for k, v in local_statuses.items():
                statuses[k] = statuses.get(k, 0) + v
            for k, v in local_scenarios.items():
                scenario_counts[k] = scenario_counts.get(k, 0) + v
    samples = []
    sampling = True
    def sampler():
        while sampling:
            samples.append({"resource": ps_snapshot(), "db_probe_ms": db_probe(db_path)})
            time.sleep(0.5)
    sample_thread = threading.Thread(target=sampler, daemon=True)
    sample_thread.start()
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker, i) for i in range(concurrency)]
        for future in futures:
            future.result()
    elapsed = time.perf_counter() - started
    sampling = False
    sample_thread.join(timeout=1)
    total = len(latencies)
    bad = sum(v for k, v in statuses.items() if k < 200 or k >= 400)
    cpus = [s["resource"]["cpu_percent_sum"] for s in samples if s["resource"]["cpu_percent_sum"] is not None]
    rams = [s["resource"]["rss_mb_sum"] for s in samples if s["resource"]["rss_mb_sum"] is not None]
    dbs = [s["db_probe_ms"] for s in samples if s["db_probe_ms"] is not None]
    return {
        "concurrency": concurrency,
        "duration_s": round(elapsed, 3),
        "think_ms": think_ms,
        "requests": total,
        "rps": round(total / elapsed, 2) if elapsed else None,
        "p50_ms": round(percentile(latencies, 50), 2) if latencies else None,
        "p95_ms": round(percentile(latencies, 95), 2) if latencies else None,
        "p99_ms": round(percentile(latencies, 99), 2) if latencies else None,
        "max_ms": round(max(latencies), 2) if latencies else None,
        "error_rate_percent": round(bad * 100 / total, 3) if total else 100.0,
        "status_counts": statuses,
        "scenario_counts": scenario_counts,
        "cpu_percent_max": round(max(cpus), 2) if cpus else None,
        "cpu_percent_avg": round(statistics.mean(cpus), 2) if cpus else None,
        "ram_mb_max": round(max(rams), 2) if rams else None,
        "ram_mb_avg": round(statistics.mean(rams), 2) if rams else None,
        "db_probe_ms_max": round(max(dbs), 3) if dbs else None,
        "db_probe_ms_avg": round(statistics.mean(dbs), 3) if dbs else None,
        "samples": len(samples),
        "login_errors": errors[:20],
    }
def start_server(port, workers, threads, db_path):
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"sqlite:///{db_path}",
        "SECRET_KEY": "capacity-synthetic-secret",
        "FLASK_ENV": "testing",
        "WEB_CONCURRENCY": str(workers),
        "GUNICORN_THREADS": str(threads),
        "GUNICORN_BIND": f"127.0.0.1:{port}",
        "GUNICORN_TIMEOUT": "30",
        "RATELIMIT_STORAGE_URI": "memory://",
        "PAYMENT_MODE": "mock",
    })
    return subprocess.Popen(
        [str(ROOT / ".venv/bin/gunicorn"), "-c", str(ROOT / "gunicorn.conf.py"), "wsgi:application"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True,
        start_new_session=True,
    )


def stop_server(proc):
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=8)
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
    try:
        proc.wait(timeout=3)
    except Exception:
        pass


ACTIVE_PROCESSES = set()


def _cleanup_active_processes(signum, frame):
    for proc in list(ACTIVE_PROCESSES):
        stop_server(proc)
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGINT, _cleanup_active_processes)
    signal.signal(signal.SIGTERM, _cleanup_active_processes)
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="1x2,2x2,2x4,4x2,4x4")
    parser.add_argument("--duration", type=float, default=12)
    parser.add_argument("--think-ms", type=int, default=350)
    parser.add_argument("--soak-duration", type=float, default=45)
    parser.add_argument("--soak-concurrency", type=int, default=16)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--candidate-p95-ms", type=float, default=1500)
    parser.add_argument("--port", type=int, default=18180)
    parser.add_argument("--output", default="runtime_logs/capacity_authenticated_matrix.json")
    args = parser.parse_args()
    email = "capacity.synthetic@example.com"
    password = os.getenv("KEMET_CAPACITY_TEST_PASSWORD") or secrets.token_urlsafe(24)
    db_path = str(ROOT / "capacity-synthetic.db")
    seed_db(db_path, email, password)
    results = []
    base = f"http://127.0.0.1:{args.port}"
    cookie_values = None
    try:
        for item in [x.strip() for x in args.matrix.split(",") if x.strip()]:
            workers, threads = [int(v) for v in item.split("x", 1)]
            proc = start_server(args.port, workers, threads, db_path)
            ACTIVE_PROCESSES.add(proc)
            try:
                if not wait_ready(base):
                    raise RuntimeError(f"server_not_ready_{workers}x{threads}")
                bootstrap = requests.Session()
                if not login(bootstrap, base, email, password):
                    raise RuntimeError(f"synthetic_login_failed_{workers}x{threads}")
                cookie_values = bootstrap.cookies.get_dict()
                result = run_profile(base, max(4, min(40, workers * threads * 3)), args.duration, args.think_ms, cookie_values, args.timeout, db_path)
                result.update({"workers": workers, "threads": threads, "profile": "matrix"})
                results.append(result)
                print(json.dumps(result, sort_keys=True))
            finally:
                stop_server(proc)
                ACTIVE_PROCESSES.discard(proc)
                time.sleep(1)
        best = None
        eligible = [r for r in results if r["error_rate_percent"] == 0 and (r["p95_ms"] or 10**9) <= args.candidate_p95_ms]
        if eligible:
            best = max(eligible, key=lambda r: r["rps"] or 0)
        soak = None
        if best:
            workers = best["workers"]
            threads = best["threads"]
            proc = start_server(args.port, workers, threads, db_path)
            ACTIVE_PROCESSES.add(proc)
            try:
                if not wait_ready(base):
                    raise RuntimeError("soak_server_not_ready")
                bootstrap = requests.Session()
                if not login(bootstrap, base, email, password):
                    raise RuntimeError("synthetic_soak_login_failed")
                soak = run_profile(base, args.soak_concurrency, args.soak_duration, args.think_ms, bootstrap.cookies.get_dict(), args.timeout, db_path)
                soak.update({"workers": workers, "threads": threads, "profile": "soak"})
                print(json.dumps(soak, sort_keys=True))
            finally:
                stop_server(proc)
                ACTIVE_PROCESSES.discard(proc)
    finally:
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass
    payload = {
        "schema": "kemet.capacity_authenticated_matrix.v1",
        "target": base,
        "synthetic_only": True,
        "authenticated": True,
        "scenarios": SCENARIOS,
        "matrix": results,
        "selected_candidate": best,
        "soak": soak,
        "production_claim": False,
        "limitations": [
            "Runs on Termux/Android with a cloned SQLite database.",
            "Synthetic identity and synthetic organization only; no real user secret is used.",
            "Provider, payment, messaging, publication and external execution paths are excluded.",
            "PostgreSQL production capacity remains unverified until a production-like database is available.",
        ],
    }
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"saved": str(out), "selected_candidate": best, "soak": soak}, sort_keys=True))


if __name__ == "__main__":
    main()
