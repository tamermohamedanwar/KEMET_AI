#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1

: "${DATABASE_URL:?DATABASE_URL is required}"
case "$DATABASE_URL" in
  sqlite:///*) ;;
  *) printf '%s\n' 'BOOTSTRAP FAILED: only SQLite is supported by this bootstrap gate' >&2; exit 2 ;;
esac

DB_PATH="${DATABASE_URL#sqlite:///}"
if [[ -e "$DB_PATH" ]]; then
  printf '%s\n' "BOOTSTRAP FAILED: target already exists: $DB_PATH" >&2
  exit 3
fi

printf '%s\n' 'KEMET DATABASE BOOTSTRAP v1'
printf '%s\n' 'Creating schema from current SQLAlchemy metadata, then stamping Alembic head.'
.venv/bin/flask db stamp head

printf '%s\n' '== revision =='
.venv/bin/flask db current
printf '%s\n' '== integrity =='
sqlite3 "$DB_PATH" 'PRAGMA integrity_check; PRAGMA foreign_key_check;'
printf '%s\n' 'BOOTSTRAP DATABASE PASS'
