from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any


class PostExecutionValidationError(RuntimeError):
    def __init__(self, code: str, result: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.result = result or {}


class PostExecutionValidator:
    VERSION = "1.1"
    MAX_FILES = 20
    MAX_BYTES = 256_000
    ALLOWED_ROOTS = ("app", "agent", "tests", "templates", "static")
    BLOCKED_DIRS = {".git", ".venv", "__pycache__", "runtime_logs", "instance"}

    def __init__(self, project_root: str | None = None):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[3]).resolve()

    def _path(self, relative: str) -> Path:
        value = str(relative or "").strip().replace("\\", "/")
        path = Path(value)
        if not value or path.is_absolute() or ".." in path.parts:
            raise PostExecutionValidationError("validation_path_not_allowed")
        if not path.parts or path.parts[0] not in self.ALLOWED_ROOTS:
            raise PostExecutionValidationError("validation_root_not_allowed")
        if any(part.startswith(".") or part in self.BLOCKED_DIRS for part in path.parts):
            raise PostExecutionValidationError("validation_path_not_allowed")
        target = (self.project_root / path).resolve()
        try:
            target.relative_to(self.project_root)
        except ValueError as exc:
            raise PostExecutionValidationError("validation_path_outside_project") from exc
        return target

    def validate(self, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(artifacts, list) or not artifacts or len(artifacts) > self.MAX_FILES:
            raise PostExecutionValidationError("validation_artifacts_required")
        files = []
        failures = []
        total = 0
        for item in artifacts:
            if not isinstance(item, dict):
                failures.append({"path": "", "error": "validation_artifact_invalid"})
                continue
            relative = str(item.get("path") or "").strip()
            target = self._path(relative)
            if not target.is_file():
                failures.append({"path": relative, "error": "validation_target_missing"})
                continue
            data = target.read_bytes()
            total += len(data)
            if len(data) > self.MAX_BYTES:
                failures.append({"path": relative, "error": "validation_target_too_large"})
            actual = hashlib.sha256(data).hexdigest()
            expected = hashlib.sha256(str(item.get("content", "")).encode("utf-8")).hexdigest()
            checks = {"exists": True, "sha256_matches": actual == expected}
            if target.suffix.lower() == ".py":
                try:
                    ast.parse(data.decode("utf-8"), filename=str(target))
                    checks["python_syntax"] = True
                except (SyntaxError, UnicodeDecodeError) as exc:
                    checks["python_syntax"] = False
                    failures.append({"path": relative, "error": "python_syntax_invalid", "detail": str(exc)})
            if not checks["sha256_matches"]:
                failures.append({"path": relative, "error": "validation_hash_mismatch"})
            files.append({"path": relative, "sha256": actual, "checks": checks})
        if total > self.MAX_BYTES * 2:
            failures.append({"path": "", "error": "validation_batch_too_large"})
        result = {"version": self.VERSION, "valid": not failures, "files": files, "failures": failures}
        if failures:
            raise PostExecutionValidationError("post_execution_validation_failed", result)
        return result


post_execution_validator = PostExecutionValidator()
