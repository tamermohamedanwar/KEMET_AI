#!/data/data/com.termux/files/usr/bin/bash

PROJECT="$HOME/products/Kemet_AI"
cd "$PROJECT" || exit 1

mkdir -p audit/global runtime_logs

STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT="audit/global/global_readiness_${STAMP}.txt"

{
echo "============================================================"
echo " KEMET AI — GLOBAL READINESS AUDIT"
echo "============================================================"
echo "DATE: $(date)"
echo "PROJECT: $PROJECT"
echo

echo "==================== VERSION ===================="
cat VERSION 2>/dev/null || true
echo

echo "==================== SERVICES ===================="
for item in \
"8010|Kemet AI|http://127.0.0.1:8010/login" \
"8765|Termux Agent|http://127.0.0.1:8765/health" \
"8770|ChatGPT Bridge|http://127.0.0.1:8770/health" \
"8780|Free Gateway|http://127.0.0.1:8780/health"
do
    port="${item%%|*}"
    rest="${item#*|}"
    name="${rest%%|*}"
    url="${rest#*|}"

    code="$(curl -sS -o /dev/null -w '%{http_code}' "$url" 2>/dev/null)"
    echo "$name : PORT $port : HTTP $code"
done
echo

echo "==================== PYTHON ===================="
python --version 2>&1
"$PROJECT/.venv/bin/python" --version 2>&1
echo

echo "==================== PACKAGES ===================="
"$PROJECT/.venv/bin/pip" list 2>/dev/null |
grep -Ei 'Flask|Gunicorn|SQLAlchemy|WTForms|dotenv|requests|beautiful|APScheduler|pypdf|openpyxl' || true
echo

echo "==================== PROJECT FILES ===================="
find app agent templates static tests -maxdepth 3 -type f \
2>/dev/null | sort | head -n 500
echo

echo "==================== AI ===================="
find app/providers app/services -type f 2>/dev/null | sort
echo
grep -RniE \
'openrouter|openai|ollama|gemini|provider|model|ask_ai|ai_service' \
app agent 2>/dev/null | head -n 250
echo

echo "==================== RAG ===================="
grep -RniE \
'RAG|rag|Document|DocumentChunk|chunk|embedding|knowledge|retriev' \
app 2>/dev/null | head -n 250
echo

echo "==================== AUTOMATION ===================="
grep -RniE \
'Automation|automation|workflow|ActionRegistry|execute|create_ticket|check_order|notification' \
app 2>/dev/null | head -n 300
echo

echo "==================== SUPPORT ===================="
grep -RniE \
'Ticket|TicketReply|support|conversation|inbox|handoff|escalat' \
app 2>/dev/null | head -n 300
echo

echo "==================== BILLING ===================="
grep -RniE \
'Subscription|Payment|PLAN_|price|billing|usage|limit|checkout|Paymob|Kashier' \
app 2>/dev/null | head -n 300
echo

echo "==================== SECURITY ===================="
grep -RniE \
'Authorization|Bearer|TOKEN|CSRF|login_required|permission|role|secret|password' \
app agent 2>/dev/null | head -n 350
echo

echo "==================== BRIDGE / MCP ===================="
grep -RniE \
'jsonrpc|tools/list|tools/call|/mcp|bridge|termux_agent|free_gateway' \
agent app 2>/dev/null | head -n 350
echo

echo "==================== TEST FILES ===================="
find tests -type f 2>/dev/null | sort
echo

echo "==================== PYTEST ===================="
"$PROJECT/.venv/bin/python" -m pytest -q \
--disable-warnings --maxfail=20 2>&1 | tail -n 150
echo

echo "==================== PYTHON COMPILE ===================="
"$PROJECT/.venv/bin/python" -m compileall -q app agent
echo "COMPILE_EXIT=$?"
echo

echo "==================== DATABASES ===================="
find . -maxdepth 4 -type f \
\( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) \
2>/dev/null | sort
echo

echo "==================== ROUTES ===================="
grep -RniE \
'@(app|.*bp)\.(route|get|post|put|delete|patch)' \
app 2>/dev/null | head -n 300
echo

echo "==================== FILE COUNTS ===================="
echo "PYTHON=$(find app agent -type f -name '*.py' 2>/dev/null | wc -l)"
echo "TEMPLATES=$(find templates app/templates -type f 2>/dev/null | wc -l)"
echo "STATIC=$(find static app/static -type f 2>/dev/null | wc -l)"
echo "TESTS=$(find tests -type f 2>/dev/null | wc -l)"
echo

echo "==================== GIT ===================="
git status --short 2>/dev/null || true
echo

echo "==================== AUDIT COMPLETE ===================="
echo "REPORT=$REPORT"
echo "============================================================"

} | tee "$REPORT"

echo
echo "============================================================"
echo " KEMET AI GLOBAL AUDIT FINISHED"
echo "============================================================"
echo "REPORT: $REPORT"
echo "============================================================"
