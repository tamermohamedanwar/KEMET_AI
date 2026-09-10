#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "$(dirname "$0")"

if [ -f ".env.agent" ]; then
    set -a
    . ./.env.agent
    set +a
fi

export PYTHONUNBUFFERED=1

exec "$(pwd)/.venv/bin/gunicorn" \
  -c "$(pwd)/gunicorn.conf.py" \
  "wsgi:application"
