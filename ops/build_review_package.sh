#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$HOME/storage/downloads/KEMET_AI_REVIEW_10MB.zip}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cd "$ROOT"

tar -cf - \
  --exclude='.git' --exclude='.venv' --exclude='node_modules' \
  --exclude='.kemet_runtime' --exclude='instance' --exclude='.kemet_archive' --exclude='storage' \
  --exclude='.pytest_cache' --exclude='runtime_logs' --exclude='uploads' \
  --exclude='__pycache__' --exclude='*/__pycache__' \
  --exclude='*.db' --exclude='*.sqlite' --exclude='*.sqlite3' --exclude='*.log' \
  --exclude='*.mp4' --exclude='*.mov' --exclude='*.wav' --exclude='*.onnx' --exclude='*.bin' --exclude='*.so' \
  --exclude='*.pyc' --exclude='*.zip' --exclude='*.tar.gz' \
  --exclude='.env' --exclude='.env.*' --exclude='*backup*' --exclude='*.bak*' --exclude='*_failed' \
  . | gzip -1 > "$TMP/source.tar.gz"
cp .env.example requirements-dev.txt README.md "$TMP/"
ROTATION_DOC="KEMET_SECRET_ROTATION_REQUIRED.md"
[ -f "$ROTATION_DOC" ] || ROTATION_DOC="docs/archive/handoffs/KEMET_SECRET_ROTATION_REQUIRED.md"
[ -f "$ROTATION_DOC" ] || ROTATION_DOC="docs/archive/KEMET_SECRET_ROTATION_REQUIRED.md"
cp "$ROTATION_DOC" "$TMP/"
( cd "$TMP" && zip -9 -q "$OUT" source.tar.gz .env.example requirements-dev.txt "$(basename "$ROTATION_DOC")" README.md )
printf 'Created %s (%s bytes)\n' "$OUT" "$(wc -c < "$OUT")"
