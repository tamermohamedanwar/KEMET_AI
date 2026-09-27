from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class ArtifactExecutionError(RuntimeError):
    pass


class ArtifactExecutionService:
    VERSION = "1.2"
    MAX_BYTES = 256_000
    MAX_FILES = 20
    ALLOWED_ROOTS = ("app", "agent", "tests", "templates", "static")
    BLOCKED_NAMES = {".env", ".env.local", ".env.agent", "id_rsa", "credentials.json"}
    BLOCKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
    BLOCKED_DIRS = {".git", ".venv", "__pycache__", "runtime_logs", "instance"}

    def __init__(self, project_root: str | None = None):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[3]).resolve()

    def _safe_path(self, relative: str) -> Path:
        value = str(relative or "").strip().replace("\\", "/")
        path = Path(value)
        if not value or path.is_absolute() or ".." in path.parts:
            raise ArtifactExecutionError("artifact_path_not_allowed")
        if path.name in self.BLOCKED_NAMES or path.suffix.lower() in self.BLOCKED_SUFFIXES:
            raise ArtifactExecutionError("artifact_path_not_allowed")
        if any(part.startswith(".") or part in self.BLOCKED_DIRS for part in path.parts):
            raise ArtifactExecutionError("artifact_path_not_allowed")
        if path.parts[0] not in self.ALLOWED_ROOTS:
            raise ArtifactExecutionError("artifact_root_not_allowed")
        target = (self.project_root / path).resolve()
        if self.project_root not in target.parents:
            raise ArtifactExecutionError("artifact_path_not_allowed")
        return target

    def validate(self, artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(artifacts, list) or not artifacts or len(artifacts) > self.MAX_FILES:
            raise ArtifactExecutionError("artifact_batch_invalid")
        normalized = []
        total = 0
        for item in artifacts:
            if not isinstance(item, dict) or not item.get("path") or "content" not in item:
                raise ArtifactExecutionError("artifact_binding_required")
            target = self._safe_path(item["path"])
            content = str(item["content"])
            expected_sha256 = item.get("expected_sha256")
            if expected_sha256 is not None:
                expected_sha256 = str(expected_sha256).strip().lower()
                if len(expected_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in expected_sha256):
                    raise ArtifactExecutionError("artifact_expected_hash_invalid")
            size = len(content.encode("utf-8"))
            total += size
            if size > self.MAX_BYTES:
                raise ArtifactExecutionError("artifact_too_large")
            normalized.append({"path": str(target.relative_to(self.project_root)), "content": content, "expected_sha256": expected_sha256})
        if total > self.MAX_BYTES * 2:
            raise ArtifactExecutionError("artifact_batch_too_large")
        return normalized

    def preview(self, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = self.validate(artifacts)
        entries = []
        for item in normalized:
            target = self._safe_path(item["path"])
            current_sha256 = None
            if target.exists():
                if not target.is_file():
                    raise ArtifactExecutionError("artifact_target_not_file")
                current_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
                expected = item.get("expected_sha256")
                if expected and expected != current_sha256:
                    raise ArtifactExecutionError("artifact_stale_hash")
            entries.append({"path": item["path"], "sha256": hashlib.sha256(item["content"].encode()).hexdigest(), "current_sha256": current_sha256, "expected_sha256": item.get("expected_sha256"), "bytes": len(item["content"].encode())})
        payload = {"version": self.VERSION, "type": "artifact_preview", "files": entries}
        payload["digest"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return payload

    def apply(self, artifacts: list[dict[str, Any]], *, backup: bool = True) -> dict[str, Any]:
        normalized = self.validate(artifacts)
        preview = self.preview(normalized)
        backup_dir = self.project_root / "runtime_logs" / "artifact_backups" / preview["digest"]
        changed = []
        if backup:
            backup_dir.mkdir(parents=True, exist_ok=True)
        originals = {}
        try:
            for item in normalized:
                target = self._safe_path(item["path"])
                existed = target.exists()
                if existed and not target.is_file():
                    raise ArtifactExecutionError("artifact_target_not_file")
                old_bytes = target.read_bytes() if existed else None
                originals[item["path"]] = old_bytes
                old_text = old_bytes.decode("utf-8") if old_bytes is not None else None
                if existed and old_text == item["content"]:
                    changed.append({"path": item["path"], "changed": False, "created": False})
                    continue
                if backup and existed:
                    backup_target = backup_dir / item["path"]
                    backup_target.parent.mkdir(parents=True, exist_ok=True)
                    backup_target.write_bytes(old_bytes)
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_name(f".{target.name}.kemet-tmp")
                temp.write_text(item["content"], encoding="utf-8")
                os.replace(temp, target)
                changed.append({"path": item["path"], "changed": True, "created": not existed})
        except Exception as exc:
            self.rollback(originals)
            if isinstance(exc, ArtifactExecutionError):
                raise
            raise ArtifactExecutionError("artifact_apply_failed") from exc
        result = {"version": self.VERSION, "preview_digest": preview["digest"], "files": changed, "backup": str(backup_dir) if backup else None}
        result["result_digest"] = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
        return result

    def rollback(self, originals: dict[str, bytes | None] | dict[str, Any]) -> dict[str, Any]:
        restored = []
        if isinstance(originals, dict) and "files" in originals:
            backup_root = Path(str(originals.get("backup") or ""))
            for item in originals.get("files") or []:
                relative = str(item.get("path") or "")
                target = self._safe_path(relative)
                try:
                    backup = backup_root / relative
                    if item.get("created") and not backup.exists():
                        if target.exists() and target.is_file():
                            target.unlink()
                    elif backup.is_file():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(backup.read_bytes())
                    restored.append(relative)
                except Exception:
                    continue
            return {"rollback": True, "restored": restored, "count": len(restored)}
        for relative, old_bytes in originals.items():
            target = self._safe_path(relative)
            try:
                if old_bytes is None:
                    if target.exists() and target.is_file():
                        target.unlink()
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(old_bytes)
                restored.append(relative)
            except Exception:
                continue
        return {"rollback": True, "restored": restored, "count": len(restored)}


artifact_execution = ArtifactExecutionService()
