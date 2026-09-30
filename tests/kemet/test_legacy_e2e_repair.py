import pathlib
import sqlite3
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops" / "repair_legacy_e2e_integrity.py"
LIVE_DB = ROOT / "instance" / "supportai.db"


def make_clone(tmp_path):
    clone = tmp_path / "repair.db"
    source = sqlite3.connect(LIVE_DB)
    target = sqlite3.connect(clone)
    source.backup(target)
    target.close()
    source.close()
    return clone


def run_repair(db, *args):
    return subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), str(SCRIPT), "--db", str(db), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def metrics(db):
    conn = sqlite3.connect(db)
    try:
        return {
            "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "fk": len(conn.execute("PRAGMA foreign_key_check").fetchall()),
            "approvals": conn.execute("SELECT COUNT(*) FROM automation_approvals").fetchone()[0],
        }
    finally:
        conn.close()


def test_dry_run_is_non_mutating(tmp_path):
    clone = make_clone(tmp_path)
    before = metrics(clone)
    result = run_repair(clone)
    after = metrics(clone)
    assert result.returncode == 0
    assert "REPAIR_STATE=ALREADY_REPAIRED" in result.stdout
    assert "MODE=NOOP" in result.stdout
    assert after == before


def test_apply_repairs_only_targeted_legacy_lineage(tmp_path):
    clone = make_clone(tmp_path)
    before = metrics(clone)
    result = run_repair(clone, "--apply")
    assert result.returncode == 0
    assert "REPAIR_STATE=ALREADY_REPAIRED" in result.stdout
    assert "MODE=NOOP" in result.stdout
    after = metrics(clone)
    assert after == before


def test_live_mutation_requires_explicit_guard():
    result = run_repair(LIVE_DB, "--apply")
    assert result.returncode != 0
    assert "live mutation requires --allow-live-mutation" in result.stderr
    assert metrics(LIVE_DB)["fk"] == 0
