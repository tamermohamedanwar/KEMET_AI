#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

PROJECT="$HOME/products/Kemet_AI"
cd "$PROJECT"

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$PROJECT/runtime_logs/ui_backup_$STAMP"

echo "=============================================="
echo "      KEMET AI BOS — UI UPGRADE"
echo "=============================================="

mkdir -p "$BACKUP"
mkdir -p app/static/css

echo
echo "[1/6] Backup current templates..."

if [ -d app/templates ]; then
    cp -r app/templates "$BACKUP/templates"
fi

if [ -d app/static/css ]; then
    cp -r app/static/css "$BACKUP/css"
fi

echo "Backup: $BACKUP"

echo
echo "[2/6] Creating modern Kemet design system..."

cat > app/static/css/kemet-modern.css <<'CSS'
:root {
    --km-bg: #f7f8fa;
    --km-white: #ffffff;
    --km-text: #18202a;
    --km-muted: #6b7280;
    --km-border: #e7eaf0;

    --km-primary: #5964d9;
    --km-primary-dark: #454fc2;

    --km-green: #3b9270;
    --km-orange: #c9863d;

    --km-radius: 18px;
    --km-shadow: 0 10px 35px rgba(20, 30, 45, .06);
}

* {
    box-sizing: border-box;
}

html,
body {
    margin: 0;
    padding: 0;
}

body {
    background: var(--km-bg) !important;
    color: var(--km-text) !important;
    font-family:
        Inter,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Roboto,
        Arial,
        sans-serif !important;
}

a {
    color: var(--km-primary);
    text-decoration: none;
}

a:hover {
    color: var(--km-primary-dark);
}

button,
input,
select,
textarea {
    font-family: inherit;
}

button,
.btn {
    border-radius: 12px !important;
    transition:
        transform .15s ease,
        box-shadow .15s ease,
        background .15s ease;
}

button:hover,
.btn:hover {
    transform: translateY(-1px);
}

input,
select,
textarea {
    background: var(--km-white) !important;
    color: var(--km-text) !important;
    border: 1px solid var(--km-border) !important;
    border-radius: 12px !important;
    min-height: 44px;
}

input:focus,
select:focus,
textarea:focus {
    outline: none !important;
    border-color: var(--km-primary) !important;
    box-shadow: 0 0 0 3px rgba(89, 100, 217, .10) !important;
}

.card,
.panel,
.stat-card,
.metric-card,
.dashboard-card {
    background: var(--km-white) !important;
    border: 1px solid var(--km-border) !important;
    border-radius: var(--km-radius) !important;
    box-shadow: var(--km-shadow) !important;
}

.kemet-brand {
    font-weight: 800;
    letter-spacing: -.045em;
    color: var(--km-text);
}

.kemet-brand span {
    color: var(--km-primary);
}

.kemet-auth-shell {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 28px;
    background:
        radial-gradient(
            circle at 10% 10%,
            rgba(89, 100, 217, .08),
            transparent 32%
        ),
        radial-gradient(
            circle at 90% 90%,
            rgba(59, 146, 112, .07),
            transparent 30%
        ),
        var(--km-bg);
}

.kemet-auth-card {
    width: min(430px, 100%);
    background: var(--km-white);
    border: 1px solid var(--km-border);
    border-radius: 24px;
    padding: 38px;
    box-shadow: 0 20px 60px rgba(20, 30, 45, .09);
}

.kemet-auth-title {
    margin: 18px 0 7px;
    font-size: 32px;
    line-height: 1.1;
    letter-spacing: -.045em;
}

.kemet-auth-copy {
    margin: 0 0 25px;
    color: var(--km-muted);
    line-height: 1.6;
}

.kemet-field {
    margin-bottom: 16px;
}

.kemet-field label {
    display: block;
    margin-bottom: 7px;
    color: #303846;
    font-size: 14px;
    font-weight: 650;
}

.kemet-btn-primary {
    width: 100%;
    min-height: 48px;
    border: 0 !important;
    border-radius: 12px !important;
    background: var(--km-primary) !important;
    color: white !important;
    font-weight: 700;
    cursor: pointer;
}

.kemet-btn-primary:hover {
    background: var(--km-primary-dark) !important;
}

.kemet-subscribe {
    position: fixed;
    top: 18px;
    right: 22px;
    z-index: 9999;
}

.kemet-subscribe a {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 42px;
    padding: 0 17px;
    background: white;
    border: 1px solid var(--km-border);
    border-radius: 12px;
    color: var(--km-text);
    font-size: 14px;
    font-weight: 700;
    box-shadow: 0 7px 25px rgba(20, 30, 45, .06);
}

.kemet-subscribe a:hover {
    border-color: var(--km-primary);
    color: var(--km-primary);
}

.kemet-auth-links {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-top: 16px;
    font-size: 14px;
}

.kemet-divider {
    height: 1px;
    background: var(--km-border);
    margin: 24px 0;
}

.kemet-dashboard-header {
    background: white;
    border-bottom: 1px solid var(--km-border);
}

.kemet-sidebar {
    background: white !important;
    border-right: 1px solid var(--km-border) !important;
}

.kemet-sidebar a {
    border-radius: 10px;
    color: #596273;
}

.kemet-sidebar a:hover {
    background: #f4f5ff;
    color: var(--km-primary);
}

.kemet-sidebar .active {
    background: #f0f1ff;
    color: var(--km-primary);
    font-weight: 700;
}

.kemet-page-title {
    font-size: 28px;
    line-height: 1.15;
    letter-spacing: -.04em;
    font-weight: 800;
}

.kemet-muted {
    color: var(--km-muted);
}

@media (max-width: 700px) {

    .kemet-auth-shell {
        padding: 18px;
    }

    .kemet-auth-card {
        padding: 28px 22px;
        border-radius: 20px;
    }

    .kemet-auth-title {
        font-size: 28px;
    }

    .kemet-subscribe {
        top: 12px;
        right: 12px;
    }

}
CSS

echo
echo "[3/6] Connecting design system to all HTML templates..."

python - <<'PY'
from pathlib import Path

root = Path("app/templates")

link = '<link rel="stylesheet" href="{{ url_for("static", filename="css/kemet-modern.css") }}">'

changed = 0

for path in root.rglob("*.html"):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        continue

    if "kemet-modern.css" in text:
        continue

    lower = text.lower()

    if "</head>" in lower:
        pos = lower.index("</head>")
        text = text[:pos] + "\n    " + link + "\n" + text[pos:]
        path.write_text(text, encoding="utf-8")
        changed += 1

print(f"Templates updated: {changed}")
PY

echo
echo "[4/6] Creating modern login styling..."

cat > app/static/css/kemet-login.css <<'CSS'
.kemet-login-page {
    min-height: 100vh;
    background: #f7f8fa;
}

.kemet-login-logo {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -.04em;
    color: #18202a;
}

.kemet-login-logo span {
    color: #5964d9;
}

.kemet-login-small {
    color: #6b7280;
    font-size: 14px;
}
CSS

echo
echo "[5/6] Restarting Kemet AI..."

PORT="${KEMET_PORT:-8000}"

pkill -f "gunicorn.*:${PORT}" 2>/dev/null || true

sleep 1

if [ -f wsgi.py ]; then

    nohup gunicorn \
        --bind "0.0.0.0:${PORT}" \
        --workers 1 \
        --timeout 120 \
        wsgi:application \
        > runtime_logs/gunicorn.log 2>&1 &

elif [ -f app.py ]; then

    nohup python app.py \
        > runtime_logs/app.log 2>&1 &

elif [ -f run.py ]; then

    nohup python run.py \
        > runtime_logs/app.log 2>&1 &

else

    echo "ERROR: Kemet AI entrypoint not found."
    exit 1

fi

sleep 3

echo
echo "[6/6] Kemet AI restarted."

echo
echo "=============================================="
echo "       KEMET AI BOS — UI COMPLETE"
echo "=============================================="
echo
echo "LOCAL:"
echo "http://127.0.0.1:${PORT}"
echo
echo "BACKUP:"
echo "$BACKUP"
echo
echo "تم الحفاظ على:"
echo "- Database"
echo "- AI"
echo "- CRM"
echo "- Automation"
echo "- Billing"
echo "- Support"
echo "- Admin"
echo "- BOS"
echo
echo "تم تحديث طبقة التصميم فقط."
echo
echo "=============================================="
