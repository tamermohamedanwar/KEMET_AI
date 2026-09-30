#!/usr/bin/env python3
import argparse
import datetime as dt
import pathlib
import shutil
import sqlite3
import sys

TARGET_APPROVALS = (5, 9, 10, 11, 12, 13, 14)
TARGET_ORGS = (9, 10, 11, 12, 13, 14)
E2E_TABLES = (
    "execution_evidence",
    "automation_outcomes",
    "automation_execution_ledger",
    "workflow_transition_records",
    "automation_queue_jobs",
    "automation_approvals",
    "subscriptions",
    "organizations",
)


def die(message):
    raise SystemExit(f"REPAIR_ABORTED: {message}")


def scalar(conn, sql, args=()):
    return conn.execute(sql, args).fetchone()[0]


def preconditions(conn):
    conn.execute("PRAGMA foreign_keys=ON")
    if scalar(conn, "PRAGMA integrity_check") != "ok":
        die("integrity_check is not ok")
    target_count = scalar(
        conn,
        "SELECT COUNT(*) FROM automation_approvals WHERE id IN (?,?,?,?,?,?,?)",
        TARGET_APPROVALS,
    )
    target_org_rows = conn.execute(
        "SELECT id, name, slug FROM organizations WHERE id IN (?,?,?,?,?,?) ORDER BY id",
        TARGET_ORGS,
    ).fetchall()
    e2e_orgs_present = [row for row in target_org_rows if str(row[1]).startswith("Durable E2E ") or str(row[1]).startswith("E2E ")]
    approval_5_present = scalar(conn, "SELECT COUNT(*) FROM automation_approvals WHERE id=5") > 0
    if scalar(conn, "SELECT COUNT(*) FROM pragma_foreign_key_check") == 0 and (
        target_count == 0 or (not e2e_orgs_present and not approval_5_present)
    ):
        return None
    approvals = conn.execute(
        "SELECT id, organization_id, workflow_id, execution_id FROM automation_approvals "
        "WHERE id IN (?,?,?,?,?,?,?) ORDER BY id", TARGET_APPROVALS
    ).fetchall()
    if tuple(r[0] for r in approvals) != TARGET_APPROVALS:
        die("target approval set changed")
    row5 = approvals[0]
    if tuple(row5) != (5, 1, 36, 146):
        die("approval 5 shape changed")
    if scalar(conn, "SELECT COUNT(*) FROM automation_executions WHERE id=146") != 0:
        die("execution 146 unexpectedly exists")
    if scalar(conn, "SELECT organization_id FROM automation_workflows WHERE id=36") != 8:
        die("workflow 36 lineage changed")
    for oid in TARGET_ORGS:
        row = conn.execute(
            "SELECT name, slug FROM organizations WHERE id=?", (oid,)
        ).fetchone()
        if row is None:
            die(f"organization {oid} missing")
        if not (str(row[0]).startswith("Durable E2E ") or str(row[0]).startswith("E2E ")):
            die(f"organization {oid} is not an expected E2E artifact")
    for t in E2E_TABLES:
        if t == "organizations":
            continue
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
        if "organization_id" in cols:
            bad = scalar(conn, f'SELECT COUNT(*) FROM "{t}" WHERE organization_id IN (?,?,?,?,?,?)', TARGET_ORGS)
            if t not in ("subscriptions", "automation_approvals", "automation_queue_jobs", "workflow_transition_records", "automation_execution_ledger", "automation_outcomes", "execution_evidence") and bad:
                die(f"unexpected E2E rows in {t}: {bad}")
    return approvals


def report(conn):
    print("TARGET_APPROVALS", TARGET_APPROVALS)
    print("TARGET_ORGS", TARGET_ORGS)
    for t in E2E_TABLES:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
        if "organization_id" in cols:
            n = scalar(conn, f'SELECT COUNT(*) FROM "{t}" WHERE organization_id IN (?,?,?,?,?,?)', TARGET_ORGS)
            if n:
                print(f"{t}={n}")
    print("approval_5=1")
    print("fk_violations", scalar(conn, "SELECT COUNT(*) FROM pragma_foreign_key_check"))


def backup(conn, source, backup_dir):
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"supportai.db.pre_legacy_e2e_repair_{stamp}"
    out = sqlite3.connect(dest)
    conn.backup(out)
    out.close()
    return dest


def apply_repair(conn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DELETE FROM automation_approvals WHERE id=5")
        conn.execute("DELETE FROM execution_evidence WHERE organization_id IN (?,?,?,?,?,?)", TARGET_ORGS)
        conn.execute("DELETE FROM automation_outcomes WHERE organization_id IN (?,?,?,?,?,?)", TARGET_ORGS)
        conn.execute("DELETE FROM automation_execution_ledger WHERE organization_id IN (?,?,?,?,?,?)", TARGET_ORGS)
        conn.execute("DELETE FROM workflow_transition_records WHERE organization_id IN (?,?,?,?,?,?)", TARGET_ORGS)
        conn.execute("DELETE FROM automation_queue_jobs WHERE organization_id IN (?,?,?,?,?,?)", TARGET_ORGS)
        conn.execute("DELETE FROM automation_approvals WHERE organization_id IN (?,?,?,?,?,?)", TARGET_ORGS)
        conn.execute("DELETE FROM subscriptions WHERE organization_id IN (?,?,?,?,?,?)", TARGET_ORGS)
        conn.execute("DELETE FROM organizations WHERE id IN (?,?,?,?,?,?)", TARGET_ORGS)
        if scalar(conn, "SELECT COUNT(*) FROM pragma_foreign_key_check") != 0:
            die("post-delete foreign-key violations detected")
        if scalar(conn, "PRAGMA integrity_check") != "ok":
            die("post-delete integrity_check failed")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="instance/supportai.db")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-live-mutation", action="store_true")
    parser.add_argument("--backup-dir", default="instance")
    args = parser.parse_args()
    db = pathlib.Path(args.db).resolve()
    live_db = pathlib.Path("instance/supportai.db").resolve()
    if args.apply and db == live_db and not args.allow_live_mutation:
        die("live mutation requires --allow-live-mutation")
    if not db.exists():
        die(f"database not found: {db}")
    conn = sqlite3.connect(db)
    try:
        state = preconditions(conn)
        if state is None:
            print("REPAIR_STATE=ALREADY_REPAIRED")
            print("MODE=NOOP")
            return
        print("PRECONDITIONS=PASS")
        report(conn)
        if not args.apply:
            print("MODE=DRY_RUN")
            return
        backup_path = backup(conn, db, pathlib.Path(args.backup_dir).resolve())
        print("BACKUP=", backup_path)
        apply_repair(conn)
        print("MODE=APPLY")
        report(conn)
        print("REPAIR=PASS")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
