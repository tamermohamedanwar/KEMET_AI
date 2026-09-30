"""Deterministic change-impact index for Kemet source navigation."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runtime_logs" / "change_intelligence_index.json"
SKIP = {".git", ".venv", "__pycache__", "node_modules", "instance", "runtime_logs"}


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def python_symbols(path: Path) -> tuple[list[dict], list[dict]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return [], []
    symbols = []
    references = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append({
                "name": node.name,
                "kind": type(node).__name__,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
            })
        elif isinstance(node, ast.Call):
            name = dotted(node.func)
            if name:
                references.append({"kind": "call", "target": name, "line": node.lineno})
    return (
        sorted(symbols, key=lambda item: (item["line"], item["name"])),
        sorted(references, key=lambda item: (item["line"], item["target"])),
    )


def build() -> dict:
    files = []
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP for part in path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        symbols, references = python_symbols(path)
        files.append({
            "path": rel,
            "sha256": file_digest(path),
            "symbols": symbols,
            "references": references,
        })
    files.sort(key=lambda item: item["path"])
    symbol_count = sum(len(item["symbols"]) for item in files)
    reference_count = sum(len(item["references"]) for item in files)
    payload = {
        "schema": "kemet.change_intelligence.v2",
        "source": "working-tree",
        "files": files,
        "file_count": len(files),
        "symbol_count": symbol_count,
        "reference_count": reference_count,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build()
    print(json.dumps({
        "schema": result["schema"],
        "file_count": result["file_count"],
        "symbol_count": result["symbol_count"],
        "reference_count": result["reference_count"],
    }, sort_keys=True))
