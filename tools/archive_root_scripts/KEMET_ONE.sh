#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

PROJECT="$HOME/products/Kemet_AI"
PORT="${KEMET_PORT:-8000}"
LOGDIR="$PROJECT/runtime_logs"
VENV="$PROJECT/.venv"

cd "$PROJECT"
mkdir -p "$LOGDIR"

echo "=============================================="
echo "        KEMET AI — ONE FILE CONTROL"
echo "=============================================="
echo

echo "[1] Project"
echo "PATH: $PROJECT"

echo
echo "[2] Python"
command -v python || true
python --version || true

echo
echo "[3] Virtual environment"
if [ ! -d "$VENV" ]; then
    echo "Creating .venv..."
    python -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "Python: $(python --version)"

echo
echo "[4] Installing required runtime packages"
python -m pip install --upgrade pip >/dev/null 2>&1 || true

python -m pip install \
    flask \
    flask-login \
    flask-sqlalchemy \
    flask-wtf \
    flask-migrate \
    python-dotenv \
    gunicorn \
    requests \
    beautifulsoup4 \
    apscheduler \
    openpyxl \
    pypdf \
    python-docx \
    >/dev/null 2>&1 || true

echo "Packages checked."

echo
echo "[5] Detecting application"

ENTRY=""

if [ -f app.py ]; then
    ENTRY="app.py"
elif [ -f run.py ]; then
    ENTRY="run.py"
elif [ -f wsgi.py ]; then
    ENTRY="wsgi.py"
elif [ -d app ]; then
    ENTRY="app"
fi

echo "ENTRY: ${ENTRY:-NOT_FOUND}"

if [ -z "$ENTRY" ]; then
    echo
    echo "ERROR: لم يتم العثور على نقطة تشغيل Kemet AI."
    echo
    echo "Files:"
    find . -maxdepth 2 -type f \
        ! -path "./.venv/*" \
        ! -path "./.git/*" \
        | sort | head -100
    exit 1
fi

echo
echo "[6] Python syntax check"

if ! python -m compileall -q app 2>/dev/null; then
    echo "WARNING: compile check found an issue in app/"
fi

[ -f app.py ] && python -m py_compile app.py 2>/dev/null || true
[ -f run.py ] && python -m py_compile run.py 2>/dev/null || true
[ -f wsgi.py ] && python -m py_compile wsgi.py 2>/dev/null || true

echo "Syntax check completed."

echo
echo "[7] Preparing WSGI"

if [ ! -f wsgi.py ] && [ -d app ]; then

cat > wsgi.py <<'PY'
try:
    from app import create_app
    application = create_app()
except Exception:
    try:
        from app import app as application
    except Exception as e:
        raise RuntimeError(
            "Kemet AI application could not be loaded: %s" % e
        )
PY

fi

echo
echo "[8] Stopping old Kemet process on port $PORT"

if command -v pkill >/dev/null 2>&1; then
    pkill -f "gunicorn.*:$PORT" 2>/dev/null || true
fi

sleep 1

echo
echo "[9] Starting Kemet AI"

if [ -f wsgi.py ]; then

    nohup gunicorn \
        --bind "0.0.0.0:$PORT" \
        --workers 1 \
        --timeout 120 \
        wsgi:application \
        > "$LOGDIR/gunicorn.log" 2>&1 &

elif [ -f app.py ]; then

    nohup python app.py \
        > "$LOGDIR/app.log" 2>&1 &

elif [ -f run.py ]; then

    nohup python run.py \
        > "$LOGDIR/app.log" 2>&1 &

else
    echo "ERROR: No supported application entrypoint."
    exit 1
fi

SERVER_PID=$!

echo "PID: $SERVER_PID"

echo
echo "[10] Waiting for server"

READY=0

for i in $(seq 1 20); do

    if curl -fsS \
        --max-time 2 \
        "http://127.0.0.1:$PORT/" \
        >/dev/null 2>&1; then

        READY=1
        break
    fi

    sleep 1
done

echo
echo "=============================================="

if [ "$READY" -eq 1 ]; then

    echo "        KEMET AI IS ONLINE"
    echo "=============================================="
    echo
    echo "LOCAL URL:"
    echo "http://127.0.0.1:$PORT"
    echo
    echo "STATUS: ONLINE"
    echo
    echo "LOG:"
    echo "$LOGDIR/gunicorn.log"
    echo
    echo "يمكنك الآن فتح:"
    echo "http://127.0.0.1:$PORT"

else

    echo "        KEMET AI DID NOT START"
    echo "=============================================="
    echo
    echo "STATUS: ERROR"
    echo
    echo "===== LAST LOG ====="

    if [ -f "$LOGDIR/gunicorn.log" ]; then
        tail -80 "$LOGDIR/gunicorn.log"
    elif [ -f "$LOGDIR/app.log" ]; then
        tail -80 "$LOGDIR/app.log"
    fi

fi

echo
echo "=============================================="
echo "KEMET ONE FILE FINISHED"
echo "=============================================="
