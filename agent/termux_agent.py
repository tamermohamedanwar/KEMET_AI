from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os
import subprocess
from pathlib import Path

load_dotenv(".env.agent", override=True)

app = Flask(__name__)

TOKEN = os.getenv("KEMET_AGENT_TOKEN", "")
PROJECT = Path(os.path.expanduser("~/products/Kemet_AI")).resolve()

MAX_READ_BYTES = 200_000
MAX_SEARCH_RESULTS = 50
MAX_WRITE_BYTES = 200_000

PROTECTED_FILES = {
    ".env",
    ".env.local",
    ".env.agent",
    ".git/config",
}

ALLOWED_COMMANDS = {
    "health": ["true"],
    "git_status": ["git", "status", "--short"],
    "compile": [".venv/bin/python", "-m", "compileall", "-q", "app"],
    "test_health": ["curl", "-sS", "http://127.0.0.1:8000/api/health"],
}


def authorized():
    return bool(TOKEN) and request.headers.get("Authorization") == f"Bearer {TOKEN}"


def safe_project_path(relative_path):
    relative_path = str(relative_path or "").strip()

    if not relative_path:
        raise ValueError("path_required")

    path = (PROJECT / relative_path).resolve()

    try:
        path.relative_to(PROJECT)
    except ValueError:
        raise ValueError("path_outside_project")

    if not path.is_file():
        raise ValueError("file_not_found")

    return path


def run(command):
    result = subprocess.run(
        command,
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "Kemet AI Termux Agent",
        "version": "2.0",
    })


@app.get("/commands")
def commands():
    if not authorized():
        return jsonify({
            "ok": False,
            "error": "unauthorized",
        }), 401

    return jsonify({
        "ok": True,
        "commands": sorted(
            list(ALLOWED_COMMANDS.keys())
            + ["list_files", "read_file", "search_code"]
        ),
    })


@app.post("/run")
def run_command():
    if not authorized():
        return jsonify({
            "ok": False,
            "error": "unauthorized",
        }), 401

    return jsonify({
        "ok": False,
        "error": "central_execution_gate_required",
        "message": "Direct Termux execution is disabled. Use the authorized Kemet AI execution path.",
    }), 403

    data = request.get_json(silent=True) or {}
    command_name = data.get("command")

    if command_name in ALLOWED_COMMANDS:
        result = run(ALLOWED_COMMANDS[command_name])

        return jsonify({
            "ok": result["ok"],
            "command": command_name,
            "returncode": result["returncode"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }), 200

    if command_name == "list_files":
        return list_files()

    if command_name == "read_file":
        return read_file()

    if command_name == "search_code":
        return search_code()

    return jsonify({
        "ok": False,
        "error": "command_not_allowed",
        "allowed": sorted(
            list(ALLOWED_COMMANDS.keys())
            + ["list_files", "read_file", "search_code"]
        ),
    }), 403


@app.post("/files/list")
def list_files():
    if not authorized():
        return jsonify({
            "ok": False,
            "error": "unauthorized",
        }), 401

    data = request.get_json(silent=True) or {}
    relative_path = str(data.get("path") or ".").strip()

    base = (PROJECT / relative_path).resolve()

    try:
        base.relative_to(PROJECT)
    except ValueError:
        return jsonify({
            "ok": False,
            "error": "path_outside_project",
        }), 400

    if not base.is_dir():
        return jsonify({
            "ok": False,
            "error": "directory_not_found",
        }), 404

    entries = []

    for item in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if item.name in {
            ".git",
            ".venv",
            "__pycache__",
        }:
            continue

        entries.append({
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
        })

    return jsonify({
        "ok": True,
        "path": str(base.relative_to(PROJECT)) or ".",
        "entries": entries[:200],
    })


@app.post("/files/read")
def read_file():
    if not authorized():
        return jsonify({
            "ok": False,
            "error": "unauthorized",
        }), 401

    data = request.get_json(silent=True) or {}
    relative_path = data.get("path")

    try:
        path = safe_project_path(relative_path)
    except ValueError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 400

    try:
        size = path.stat().st_size

        if size > MAX_READ_BYTES:
            return jsonify({
                "ok": False,
                "error": "file_too_large",
                "max_bytes": MAX_READ_BYTES,
                "size": size,
            }), 413

        content = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    except OSError as exc:
        return jsonify({
            "ok": False,
            "error": "read_failed",
            "detail": str(exc),
        }), 500

    return jsonify({
        "ok": True,
        "path": str(path.relative_to(PROJECT)),
        "size": size,
        "content": content,
    })


@app.post("/files/write")
def write_file():
    if not authorized():
        return jsonify({
            "ok": False,
            "error": "unauthorized",
        }), 401

    data = request.get_json(silent=True) or {}
    relative_path = str(data.get("path") or "").strip()
    content = data.get("content")

    if not relative_path:
        return jsonify({"ok": False, "error": "path_required"}), 400

    if content is None:
        return jsonify({"ok": False, "error": "content_required"}), 400

    if not isinstance(content, str):
        return jsonify({"ok": False, "error": "content_must_be_string"}), 400

    project = PROJECT.resolve()
    path = (project / relative_path).resolve()

    try:
        path.relative_to(project)
    except ValueError:
        return jsonify({"ok": False, "error": "path_outside_project"}), 400

    normalized = str(path.relative_to(project))

    if normalized in PROTECTED_FILES:
        return jsonify({"ok": False, "error": "protected_file"}), 403

    encoded_size = len(content.encode("utf-8"))

    if encoded_size > MAX_WRITE_BYTES:
        return jsonify({
            "ok": False,
            "error": "content_too_large",
            "max_bytes": MAX_WRITE_BYTES,
            "size": encoded_size,
        }), 413

    parent = path.parent.resolve()

    try:
        parent.relative_to(project)
    except ValueError:
        return jsonify({"ok": False, "error": "parent_outside_project"}), 400

    try:
        parent.mkdir(parents=True, exist_ok=True)

        backup_path = None

        if path.exists():
            if not path.is_file():
                return jsonify({
                    "ok": False,
                    "error": "target_not_file",
                }), 400

            import time
            stamp = time.strftime("%Y%m%d_%H%M%S")

            backup_path = path.with_name(
                path.name + f".backup_before_write_{stamp}"
            )

            path.replace(backup_path)

        path.write_text(content, encoding="utf-8")

    except OSError as exc:
        return jsonify({
            "ok": False,
            "error": "write_failed",
            "detail": str(exc),
        }), 500

    return jsonify({
        "ok": True,
        "path": normalized,
        "size": encoded_size,
        "backup": (
            str(backup_path.relative_to(project))
            if backup_path else None
        ),
    })


@app.post("/search")
def search_code():
    if not authorized():
        return jsonify({
            "ok": False,
            "error": "unauthorized",
        }), 401

    data = request.get_json(silent=True) or {}

    query = str(data.get("query") or "").strip()
    relative_path = str(data.get("path") or ".").strip()

    if not query:
        return jsonify({
            "ok": False,
            "error": "query_required",
        }), 400

    base = (PROJECT / relative_path).resolve()

    try:
        base.relative_to(PROJECT)
    except ValueError:
        return jsonify({
            "ok": False,
            "error": "path_outside_project",
        }), 400

    if not base.exists():
        return jsonify({
            "ok": False,
            "error": "path_not_found",
        }), 404

    results = []

    files = [base] if base.is_file() else base.rglob("*")

    excluded_dirs = {
        ".git",
        ".venv",
        "__pycache__",
    }

    for path in files:
        if len(results) >= MAX_SEARCH_RESULTS:
            break

        if not path.is_file():
            continue

        if any(part in excluded_dirs for part in path.parts):
            continue

        try:
            if path.stat().st_size > MAX_READ_BYTES:
                continue

            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue

        for line_number, line in enumerate(text.splitlines(), 1):
            if query.lower() in line.lower():
                results.append({
                    "file": str(path.relative_to(PROJECT)),
                    "line": line_number,
                    "text": line[:1000],
                })

                if len(results) >= MAX_SEARCH_RESULTS:
                    break

    return jsonify({
        "ok": True,
        "query": query,
        "results": results,
        "count": len(results),
        "truncated": len(results) >= MAX_SEARCH_RESULTS,
    })


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8765,
        debug=False,
    )
