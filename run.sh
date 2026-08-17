#!/data/data/com.termux/files/usr/bin/bash

cd "$(dirname "$0")"

source .venv/bin/activate

gunicorn -w 4 -b 0.0.0.0:5000 app:create_app()
