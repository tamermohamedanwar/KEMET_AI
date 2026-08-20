#!/data/data/com.termux/files/usr/bin/bash

cd "$HOME/products/Kemet_AI" || exit 1
source .venv/bin/activate

exec "$PWD/.venv/bin/gunicorn" \
    -w 1 \
    -b 127.0.0.1:5001 \
    --access-logfile "$PWD/logs/access.log" \
    --error-logfile "$PWD/logs/error.log" \
    "app:create_app()"
