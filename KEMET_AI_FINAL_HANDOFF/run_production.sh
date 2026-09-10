#!/data/data/com.termux/files/usr/bin/bash

set -e

cd "$(dirname "$0")"

if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
fi

export PYTHONUNBUFFERED=1

exec gunicorn -c gunicorn.conf.py "app:create_app()"
