"""Local-only agentic security hypothesis generator for Kemet.

The tool performs deterministic AST analysis only. It never sends network
traffic, invokes discovered sinks, or grants execution authority.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runtime_logs" / "security_agent_review.json"
INDEX = ROOT / "runtime_logs" / "change_intelligence_index.json"
SKIP = {".git", ".venv", "__pycache__", "instance", "runtime_logs", "uploads"}
TEST_PARTS = {"test", "tests", "fixtures", "fixture", "snapshots"}

RULES = {
    "command-execution": {"subprocess", "os.system", "os.popen"},
    "dynamic-code": {"eval", "exec"},
    "unsafe-deserialization": {"pickle.load", "pickle.loads"},
    "unsafe-yaml": {"yaml.load"},
}

SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{12,}['\"]"
)
TEMPLATE_MARKERS = ("{{", "}}", "csrf_token", "get_flashed_messages")


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def file_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def line_digest(line: str) -> str:
    return hashlib.sha256(line.strip().encode("utf-8")).hexdigest()


def is_test_path(path: Path) -> bool:
    return any(part.lower() in TEST_PARTS for part in path.parts)


def classify_path(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    if is_test_path(path) or rel.startswith("ops/capacity_"):
        return "test_or_fixture"
    return "production_code"


def nearest_symbol(tree: ast.AST, line: int) -> str | None:
    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = getattr(node, "lineno", 0)
            end = getattr(node, "end_lineno", start)
            if start <= line <= end:
                candidates.append((start, end, node.name))
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[1] - item[0], -item[0]))[2]


def hypothesis_id(path: str, category: str, line: int, evidence: str) -> str:
    raw = f"{path}|{category}|{line}|{line_digest(evidence)}"
    return "sec_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def make_hypothesis(path: Path, source: str, tree: ast.AST, category: str,
                    symbol: str, line: int, evidence: str, reason: str) -> dict:
    rel = path.relative_to(ROOT).as_posix()
    kind = classify_path(path)
    return {
        "hypothesis_id": hypothesis_id(rel, category, line, evidence),
        "category": category,
        "symbol": symbol,
        "line": line,
        "source_digest": file_digest(source),
        "evidence_digest": line_digest(evidence),
        "evidence": evidence.strip()[:300],
        "reason": reason,
        "code_class": kind,
        "confidence": "low",
        "validation_status": "hypothesis",
        "human_review_required": True,
        "execution_authority": False,
        "network": False,
        "caller_symbol": nearest_symbol(tree, line),
        "affected_control": None,
        "regression_test": None,
        "remediation_status": "open",
    }


def inspect(path: Path) -> list[dict]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    lines = source.splitlines()
    hypotheses = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = dotted(node.func)
        evidence = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else name
        for category, needles in RULES.items():
            if name in needles or any(name.startswith(f"{n}.") for n in needles):
                hypotheses.append(make_hypothesis(
                    path, source, tree, category, name, node.lineno, evidence,
                    "Sensitive sink or dynamic operation requires source-level validation.",
                ))
        if name == "subprocess.run":
            shell_true = any(
                kw.arg == "shell" and isinstance(kw.value, ast.Constant)
                and kw.value.value is True for kw in node.keywords
            )
            if shell_true:
                hypotheses.append(make_hypothesis(
                    path, source, tree, "shell-execution", name, node.lineno, evidence,
                    "subprocess.run uses shell=True and requires command-boundary validation.",
                ))
    for line_no, line in enumerate(lines, 1):
        match = SECRET_RE.search(line)
        if not match or "os.getenv" in line or "os.environ" in line:
            continue
        if any(marker in line for marker in TEMPLATE_MARKERS):
            continue
        category = "test-fixture-secret" if classify_path(path) == "test_or_fixture" else "possible-hardcoded-secret"
        hypotheses.append(make_hypothesis(
            path, source, tree, category, "literal-assignment", line_no, line,
            "Literal credential-like assignment requires classification and secret-store review.",
        ))
    return sorted(hypotheses, key=lambda item: (item["line"], item["category"], item["hypothesis_id"]))


def load_change_index() -> dict:
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def symbol_map(index: dict) -> dict[str, list[str]]:
    result = {}
    for item in index.get("files", []):
        result[item.get("path", "")] = [s.get("name") for s in item.get("symbols", [])]
    return result


def build() -> dict:
    index = load_change_index()
    indexed = symbol_map(index)
    files = []
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP for part in path.parts):
            continue
        hits = inspect(path)
        if not hits:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for hit in hits:
            hit["indexed_file"] = rel in indexed
            hit["symbol_index_available"] = hit["caller_symbol"] in indexed.get(rel, []) if hit["caller_symbol"] else False
        files.append({"path": rel, "hypotheses": hits})
    files.sort(key=lambda item: item["path"])
    categories: dict[str, int] = {}
    classes: dict[str, int] = {}
    for item in files:
        for hit in item["hypotheses"]:
            categories[hit["category"]] = categories.get(hit["category"], 0) + 1
            classes[hit["code_class"]] = classes.get(hit["code_class"], 0) + 1
    return {
        "schema": "kemet.security_agent_review.v2",
        "network": False,
        "execution": False,
        "human_review_required": True,
        "finding_promotion_requires": ["source_evidence", "focused_test", "regression_proof"],
        "change_intelligence_schema": index.get("schema"),
        "files": files,
        "categories": categories,
        "code_classes": classes,
        "hypothesis_count": sum(categories.values()),
    }


def main() -> int:
    result = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "schema": result["schema"],
        "hypothesis_count": result["hypothesis_count"],
        "categories": result["categories"],
        "code_classes": result["code_classes"],
        "network": result["network"],
        "execution": result["execution"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def inspect_source(source: str, relative_path: str = "app/security_fixture.py") -> list[dict]:
    path = ROOT / relative_path
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    hypotheses = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = dotted(node.func)
        evidence = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else name
        for category, needles in RULES.items():
            if name in needles or any(name.startswith(f"{n}.") for n in needles):
                hypotheses.append(make_hypothesis(
                    path, source, tree, category, name, node.lineno, evidence,
                    "Sensitive sink or dynamic operation requires source-level validation.",
                ))
        if name == "subprocess.run":
            shell_true = any(
                kw.arg == "shell" and isinstance(kw.value, ast.Constant)
                and kw.value.value is True for kw in node.keywords
            )
            if shell_true:
                hypotheses.append(make_hypothesis(
                    path, source, tree, "shell-execution", name, node.lineno, evidence,
                    "subprocess.run uses shell=True and requires command-boundary validation.",
                ))
    for line_no, line in enumerate(lines, 1):
        match = SECRET_RE.search(line)
        if not match or "os.getenv" in line or "os.environ" in line:
            continue
        if any(marker in line for marker in TEMPLATE_MARKERS):
            continue
        category = "test-fixture-secret" if classify_path(path) == "test_or_fixture" else "possible-hardcoded-secret"
        hypotheses.append(make_hypothesis(
            path, source, tree, category, "literal-assignment", line_no, line,
            "Literal credential-like assignment requires classification and secret-store review.",
        ))
    return sorted(hypotheses, key=lambda item: (item["line"], item["category"], item["hypothesis_id"]))
