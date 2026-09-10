#!/data/data/com.termux/files/usr/bin/sh

cd /data/data/com.termux/files/home/products/Kemet_AI

. .venv/bin/activate

exec gunicorn -w 1 -b 0.0.0.0:5000 "app:create_app()"
