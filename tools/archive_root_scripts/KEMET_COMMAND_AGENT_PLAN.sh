#!/data/data/com.termux/files/usr/bin/bash

set -e

PROJECT="$HOME/products/Kemet_AI"

echo "======================================"
echo " KEMET AI COMMAND AGENT"
echo "======================================"

echo
echo "Bridge:"
curl -fsS "$TUNNEL_URL/health" || true

echo
echo
echo "Available execution endpoint:"
echo "POST $TUNNEL_URL/run"

echo
echo "Allowed commands currently:"
curl -fsS \
  -H "Authorization: Bearer $KEMET_AGENT_TOKEN" \
  "$TUNNEL_URL/commands"

echo
echo
echo "======================================"
echo " CONNECTION READY"
echo "======================================"
echo
echo "Kemet AI page can now use the Bridge"
echo "without MCP."
echo
echo "Next layer:"
echo "Natural language -> command planner -> /run -> Termux"
echo
