"""Build a local security-hypothesis to code-intelligence impact map."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "runtime_logs" / "security_agent_review.json"
INDEX = ROOT / "runtime_logs" / "change_intelligence_index.json"
OUT = ROOT / "runtime_logs" / "security_impact_map.json"


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build() -> dict:
    security = load(SECURITY)
    index = load(INDEX)
    files = {item.get("path"): item for item in index.get("files", [])}
    impacts = []
    for file_item in security.get("files", []):
        path = file_item.get("path")
        index_item = files.get(path, {})
        refs = index_item.get("references", [])
        symbols = index_item.get("symbols", [])
        for hypothesis in file_item.get("hypotheses", []):
            caller = hypothesis.get("caller_symbol")
            related_refs = []
            if caller:
                caller_meta = next((item for item in symbols if item.get("name") == caller), None)
                start = caller_meta.get("line", 0) if caller_meta else 0
                end = caller_meta.get("end_line", 0) if caller_meta else 0
                for ref in refs:
                    if start <= ref.get("line", 0) <= end:
                        related_refs.append(ref)
            impacts.append({
                "hypothesis_id": hypothesis.get("hypothesis_id"),
                "path": path,
                "line": hypothesis.get("line"),
                "caller_symbol": caller,
                "symbol_index_available": hypothesis.get("symbol_index_available", False),
                "file_sha256": index_item.get("sha256"),
                "file_symbol_count": len(symbols),
                "related_references": related_refs[:50],
            })
    impacts.sort(key=lambda item: item["hypothesis_id"] or "")
    result = {
        "schema": "kemet.security_impact_map.v1",
        "change_intelligence_schema": index.get("schema"),
        "security_schema": security.get("schema"),
        "hypothesis_count": len(impacts),
        "impacts": impacts,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


if __name__ == "__main__":
    result = build()
    print(json.dumps({
        "schema": result["schema"],
        "hypothesis_count": result["hypothesis_count"],
    }, sort_keys=True))
