#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

PROJECT="$HOME/products/Kemet_AI"
cd "$PROJECT"

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$HOME/products/Kemet_AI_backups/Kemet_Command_Center_$STAMP"
REPORT="runtime_logs/kemet_command_center_$STAMP.log"

mkdir -p "$BACKUP" runtime_logs

exec > >(tee -a "$REPORT") 2>&1

echo "=============================================="
echo " KEMET PACK 02 — COMMAND CENTER"
echo "=============================================="

echo "[1/10] Creating safety backup..."

if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude='.venv/' \
      --exclude='venv/' \
      --exclude='__pycache__/' \
      --exclude='*.pyc' \
      --exclude='*.log' \
      --exclude='runtime_logs/' \
      --exclude='.git/' \
      ./ "$BACKUP/"
else
    tar \
      --exclude='.venv' \
      --exclude='venv' \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='*.log' \
      --exclude='runtime_logs' \
      --exclude='.git' \
      -cf - . | tar -C "$BACKUP" -xf -
fi

echo "BACKUP=$BACKUP"

echo
echo "[2/10] Inspecting current Kemet structure..."

echo "--- ROUTES ---"
find app -type f \( -name "*.py" -o -name "*.html" \) | sort | head -250

echo
echo "--- TEMPLATES ---"
find app/templates -type f 2>/dev/null | sort | head -200 || true

echo
echo "[3/10] Creating Command Center directories..."

mkdir -p \
    app/core/command_center \
    app/templates/kemet \
    app/static/kemet \
    tests/kemet

echo "[4/10] Creating Command Center service..."

cat > app/core/command_center/service.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CommandCenterSnapshot:
    revenue: float = 0.0
    customers: int = 0
    leads: int = 0
    open_issues: int = 0
    automations_running: int = 0
    ai_actions: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "revenue": self.revenue,
            "customers": self.customers,
            "leads": self.leads,
            "open_issues": self.open_issues,
            "automations_running": self.automations_running,
            "ai_actions": self.ai_actions,
        }


class CommandCenterService:

    def snapshot(self, organization_id=None) -> CommandCenterSnapshot:
        """
        Safe initial snapshot.

        Existing database models/services are intentionally not modified
        in PACK 02. Later packs will connect real business metrics here.
        """
        return CommandCenterSnapshot()
PY

echo "[5/10] Creating Command Center blueprint..."

cat > app/core/command_center/__init__.py <<'PY'
from .service import CommandCenterService, CommandCenterSnapshot

__all__ = [
    "CommandCenterService",
    "CommandCenterSnapshot",
]
PY

echo "[6/10] Creating global Command Center UI..."

cat > app/templates/kemet/command_center.html <<'HTML'
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <title>Kemet Command Center</title>

    <style>
        :root {
            --bg: #f7f7f5;
            --surface: #ffffff;
            --text: #171717;
            --muted: #737373;
            --border: #e5e5e5;
            --accent: #111111;
            --success: #166534;
            --warning: #92400e;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family:
                Inter,
                ui-sans-serif,
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
        }

        .shell {
            max-width: 1400px;
            margin: auto;
            padding: 32px 22px 60px;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            gap: 20px;
            margin-bottom: 28px;
        }

        .eyebrow {
            font-size: 12px;
            letter-spacing: .16em;
            text-transform: uppercase;
            color: var(--muted);
            font-weight: 700;
        }

        h1 {
            margin: 7px 0 5px;
            font-size: clamp(30px, 5vw, 54px);
            letter-spacing: -.04em;
        }

        .subtitle {
            color: var(--muted);
            font-size: 15px;
        }

        .brand {
            font-weight: 800;
            letter-spacing: .08em;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 14px;
        }

        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 20px;
        }

        .metric {
            grid-column: span 2;
            min-height: 130px;
        }

        .metric-label {
            color: var(--muted);
            font-size: 13px;
            margin-bottom: 12px;
        }

        .metric-value {
            font-size: 32px;
            font-weight: 800;
            letter-spacing: -.03em;
        }

        .wide {
            grid-column: span 3;
            min-height: 250px;
        }

        .full {
            grid-column: 1 / -1;
        }

        .card h2 {
            font-size: 18px;
            margin: 0 0 8px;
        }

        .card p {
            color: var(--muted);
            line-height: 1.6;
        }

        .recommendation {
            display: flex;
            justify-content: space-between;
            gap: 15px;
            padding: 14px 0;
            border-top: 1px solid var(--border);
        }

        .recommendation:first-of-type {
            border-top: 0;
        }

        .pill {
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 7px 10px;
            font-size: 12px;
            white-space: nowrap;
        }

        .footer {
            margin-top: 28px;
            color: var(--muted);
            font-size: 13px;
        }

        @media (max-width: 900px) {
            .grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .metric,
            .wide {
                grid-column: span 1;
            }

            .full {
                grid-column: 1 / -1;
            }
        }

        @media (max-width: 560px) {
            .grid {
                grid-template-columns: 1fr;
            }

            .metric,
            .wide,
            .full {
                grid-column: 1;
            }

            .header {
                align-items: flex-start;
                flex-direction: column;
            }
        }
    </style>
</head>

<body>
<main class="shell">

    <header class="header">
        <div>
            <div class="eyebrow">AI Business Operating System</div>
            <h1>Command Center</h1>
            <div class="subtitle">
                Your business at a glance.
            </div>
        </div>

        <div class="brand">KEMET</div>
    </header>

    <section class="grid">

        <article class="card metric">
            <div class="metric-label">Revenue</div>
            <div class="metric-value">{{ snapshot.revenue }}</div>
        </article>

        <article class="card metric">
            <div class="metric-label">Customers</div>
            <div class="metric-value">{{ snapshot.customers }}</div>
        </article>

        <article class="card metric">
            <div class="metric-label">Leads</div>
            <div class="metric-value">{{ snapshot.leads }}</div>
        </article>

        <article class="card metric">
            <div class="metric-label">Open Issues</div>
            <div class="metric-value">{{ snapshot.open_issues }}</div>
        </article>

        <article class="card metric">
            <div class="metric-label">Automations Running</div>
            <div class="metric-value">{{ snapshot.automations_running }}</div>
        </article>

        <article class="card metric">
            <div class="metric-label">AI Actions</div>
            <div class="metric-value">{{ snapshot.ai_actions }}</div>
        </article>

        <article class="card wide">
            <h2>Kemet Intelligence</h2>
            <p>
                Kemet will continuously understand your business,
                identify opportunities and surface the actions that
                deserve your attention.
            </p>

            <div class="recommendation">
                <span>Business intelligence layer</span>
                <span class="pill">Preparing</span>
            </div>

            <div class="recommendation">
                <span>Opportunity detection</span>
                <span class="pill">Preparing</span>
            </div>
        </article>

        <article class="card wide">
            <h2>Kemet Execution</h2>
            <p>
                The execution layer will turn approved decisions into
                real business actions while keeping every action auditable.
            </p>

            <div class="recommendation">
                <span>Automations</span>
                <span class="pill">Connected next</span>
            </div>

            <div class="recommendation">
                <span>AI actions</span>
                <span class="pill">Connected next</span>
            </div>
        </article>

        <article class="card full">
            <h2>Kemet Recommends</h2>

            <div class="recommendation">
                <span>Connect real CRM and revenue metrics</span>
                <span class="pill">Next</span>
            </div>

            <div class="recommendation">
                <span>Connect automation execution metrics</span>
                <span class="pill">Next</span>
            </div>

            <div class="recommendation">
                <span>Activate Kemet Intelligence</span>
                <span class="pill">PACK 03</span>
            </div>
        </article>

    </section>

    <div class="footer">
        Don't use another AI tool. Run your business with Kemet.
    </div>

</main>
</body>
</html>
HTML

echo "[7/10] Creating isolated route module..."

cat > app/core/command_center/route_factory.py <<'PY'
from __future__ import annotations

from flask import Blueprint, render_template

from .service import CommandCenterService


def create_command_center_blueprint():
    blueprint = Blueprint(
        "kemet_command_center",
        __name__,
        url_prefix="/kemet",
    )

    service = CommandCenterService()

    @blueprint.get("/command-center")
    def command_center():
        snapshot = service.snapshot()
        return render_template(
            "kemet/command_center.html",
            snapshot=snapshot,
        )

    return blueprint
PY

echo "[8/10] Creating test..."

cat > tests/kemet/test_command_center.py <<'PY'
from app.core.command_center.service import (
    CommandCenterService,
    CommandCenterSnapshot,
)


def test_snapshot_contract():
    snapshot = CommandCenterService().snapshot()

    assert isinstance(snapshot, CommandCenterSnapshot)
    assert snapshot.revenue == 0.0
    assert snapshot.customers == 0
    assert snapshot.leads == 0


def test_snapshot_serialization():
    snapshot = CommandCenterSnapshot(
        revenue=100,
        customers=5,
        leads=3,
    )

    data = snapshot.as_dict()

    assert data["revenue"] == 100
    assert data["customers"] == 5
    assert data["leads"] == 3
PY

echo "[9/10] Running validation..."

PYTHON=".venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    PYTHON="$(command -v python)"
fi

"$PYTHON" -m compileall -q \
    app/core/command_center \
    tests/kemet

"$PYTHON" - <<'PY'
from app.core.command_center.service import CommandCenterService

snapshot = CommandCenterService().snapshot()

assert snapshot.as_dict()["customers"] == 0

print("KEMET_COMMAND_CENTER_TEST=PASS")
PY

echo
echo "[10/10] Checking existing application..."

if [ -f wsgi.py ]; then

    "$PYTHON" - <<'PY'
import wsgi

application = getattr(wsgi, "application", None)
app = getattr(wsgi, "app", None)

assert application is not None or app is not None

print("KEMET_WSGI_IMPORT=PASS")
PY

else
    echo "WSGI file not found — skipped."
fi

cat > "KEMET_PACK_02_STATUS_$STAMP.txt" <<EOF
KEMET PACK 02 — COMMAND CENTER

Timestamp: $STAMP

Backup:
$BACKUP

Created:
app/core/command_center/
app/templates/kemet/command_center.html
tests/kemet/test_command_center.py

Database modified: NO
.env modified: NO
Existing core application overwritten: NO

Validation:
KEMET_COMMAND_CENTER_TEST=PASS
EOF

echo
echo "=============================================="
echo " KEMET PACK 02 — FOUNDATION READY"
echo "=============================================="
echo
echo "Backup:"
echo "$BACKUP"
echo
echo "Route module prepared:"
echo "/kemet/command-center"
echo
echo "IMPORTANT:"
echo "The existing application has NOT been force-modified."
echo "The Command Center route is isolated until integrated."
echo
echo "Next step:"
echo "Connect the Command Center safely to the existing Flask app."
echo "=============================================="
