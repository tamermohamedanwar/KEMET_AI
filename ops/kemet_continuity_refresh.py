#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
KEY = ROOT / "KEMET_PROFIT_CONTINUUM_MASTER_KEY.md"
START = "<!-- AUTO_SURFACE_START -->"
END = "<!-- AUTO_SURFACE_END -->"

EXCLUDE_PARTS = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache"}
SOURCE_ROOTS = ("app", "agent", "ops", "tests", "migrations", "scripts")
def files_under(root: pathlib.Path):
    for base in SOURCE_ROOTS:
        d = root / base
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and not any(x in EXCLUDE_PARTS for x in p.parts):
                yield p

def git(cmd):
    try:
        return subprocess.check_output(
            ["git", *cmd], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unavailable"

def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def inventory():
    fs = list(files_under(ROOT))
    rel = [p.relative_to(ROOT).as_posix() for p in fs]
    ext = {}
    for x in rel:
        e = pathlib.Path(x).suffix.lower() or "[no extension]"
        ext[e] = ext.get(e, 0) + 1

    groups = {
        "Agent / Intelligence": r"agent|intelligence|reasoning|decision|planner|federation|memory|rag",
        "Business / CRM / Revenue": r"crm|lead|sales|customer|offer|payment|revenue|billing|commerce|profit|subscription",
        "Automation / Jobs / Workforce": r"automation|job|queue|worker|workflow|schedule|workforce|orchestrat",
        "Media / Content / Production": r"media|content|cinematic|mendes|production|video|shot|story|visual|voice|audio|render|generation",
        "Channels / Integrations": r"telegram|whatsapp|omnichannel|channel|oauth|connector|social|youtube|tiktok|salla|google",
        "Documents / Knowledge": r"document|ingest|file|rag|knowledge|spreadsheet|invoice",
        "Security / Governance / Evidence": r"security|auth|approval|gate|execution|evidence|provenance|audit|tenant|policy|secret|rate_limit",
        "Reliability / Operations": r"observability|telemetry|reliability|capacity|health|readiness|release|deployment|runtime|ops",
        "UI / Command Center": r"template|dashboard|command_center|command_agent|static|forms|ui",
        "ML / Evaluation": r"ml_|evaluation|dataset|generalization|model_",
    }
    counts = {}
    examples = {}
    for name, pat in groups.items():
        hits = [x for x in rel if re.search(pat, x, re.I)]
        counts[name] = len(hits)
        examples[name] = hits[:8]

    docs = sorted(str(p.relative_to(ROOT)) for p in ROOT.glob("*.md"))
    tests = [x for x in rel if x.startswith("tests/")]
    migrations = [x for x in rel if x.startswith("migrations/versions/")]
    digest = sha("\n".join(sorted(rel)))

    return fs, rel, ext, counts, examples, docs, len(tests), len(migrations), digest
def render():
    fs, rel, ext, counts, examples, docs, test_count, migration_count, digest = inventory()
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        START,
        "## AUTO-DISCOVERED PROJECT SURFACE",
        f"Generated: {now}",
        f"Inventory digest: {digest}",
        f"Tracked source/ops/test files discovered: {len(fs)}",
        f"Test files discovered: {test_count}",
        f"Migration files discovered: {migration_count}",
        "",
        "This section is generated from the live repository and is intentionally",
        "non-authoritative for capability readiness. It detects new project work",
        "automatically; readiness still requires live runtime/evidence verification.",
        "",
        "### Detected capability surfaces",
    ]
    for name, count in counts.items():
        lines.append(f"- {name}: {count} matching files")
        if examples[name]:
            lines.append("  - " + "; ".join(examples[name]))
    lines += ["", "### Source file mix"]
    for e, n in sorted(ext.items(), key=lambda z: (-z[1], z[0]))[:20]:
        lines.append(f"- {e}: {n}")
    lines += [
        "",
        "### Canonical operating rule for future development",
        "Every continuation invocation MUST re-run this discovery before deciding",
        "whether a capability is new, existing, changed, stale, blocked, or verified.",
        "New files do not automatically become READY; they become DISCOVERED until",
        "implementation, tests, runtime behavior, provenance, and governance are verified.",
        END,
    ]
    return "\n".join(lines) + "\n"
def apply():
    current = KEY.read_text(encoding="utf-8")
    block = render()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END) + r"\n?", re.S)
    if pattern.search(current):
        updated = pattern.sub(block, current, count=1)
    else:
        updated = current.rstrip() + "\n\n" + block
    KEY.write_text(updated, encoding="utf-8")
    return block

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    block = render()
    if args.apply:
        apply()
        print("CONTINUITY_REFRESH=APPLIED")
    else:
        print("CONTINUITY_REFRESH=PREVIEW")
    print(block, end="")
    print(f"GIT_HEAD={git(['rev-parse', 'HEAD'])}")
    print(f"GIT_BRANCH={git(['branch', '--show-current'])}")
    if args.check:
        text = KEY.read_text(encoding="utf-8")
        print("KEY_AUTO_SURFACE=OK" if START in text and END in text else "KEY_AUTO_SURFACE=MISSING")

if __name__ == "__main__":
    main()
