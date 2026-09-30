#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
cd "$ROOT"

usage() {
  echo "Usage: $0 {auto|snapshot|fast|social|content|security|integration|smoke|release|full}"
  exit 2
}

run_pytest() { "$PY" -m pytest -q "$@"; }

fast() {
  "$PY" -m compileall -q app agent
  git diff --check
}

social() {
  run_pytest tests/kemet/test_social_publishing_adapters.py tests/kemet/test_social_publishing_governance.py tests/kemet/test_social_connection_service.py tests/kemet/test_social_channel_readiness.py
}

content() {
  run_pytest tests/kemet/test_command_center.py tests/kemet/test_content_factory_service.py tests/kemet/test_content_social_governance.py
}

security() {
  run_pytest tests/kemet/test_unified_approval_execution.py tests/kemet/test_security_controls.py tests/kemet/test_secret_boundary_regression.py tests/kemet/test_trust_architecture.py
}

integration() {
  run_pytest tests/kemet/test_content_social_governance.py tests/kemet/test_social_publishing_adapters.py tests/kemet/test_social_measurement.py tests/kemet/test_commercial_outcome_trace.py tests/kemet/test_revenue_command_governance.py
}
smoke() {
  curl -fsS http://127.0.0.1:5000/api/health >/dev/null
  test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5000/mcp)" = "404"
}

release() {
  fast
  security
  integration
  smoke
  run_pytest tests/kemet/test_release_hardening_gate.py
}

full() {
  fast
  run_pytest
}

snapshot() {
  local baseline="$ROOT/.git/kemet_verification_baseline"
  : > "$baseline"
  while IFS= read -r path; do
    [ -f "$path" ] || continue
    printf '%s  %s\n' "$(sha256sum "$path" | awk '{print $1}')" "$path" >> "$baseline"
  done < <(git ls-files -co --exclude-standard | sort -u)
  printf 'VERIFICATION_PIPELINE_SNAPSHOT files=%s\n' "$(wc -l < "$baseline")"
}

auto() {
  fast
  local baseline="$ROOT/.git/kemet_verification_baseline"
  mapfile -t current < <(git ls-files -co --exclude-standard | sort -u)
  local -a changed=()
  if [ -f "$baseline" ]; then
    declare -A seen=()
    while read -r digest path; do seen["$path"]="$digest"; done < "$baseline"
    local path digest
    for path in "${current[@]}"; do
      [ -f "$path" ] || continue
      digest="$(sha256sum "$path" | awk '{print $1}')"
      if [ "${seen[$path]:-}" != "$digest" ]; then changed+=("$path"); fi
    done
    for path in "${!seen[@]}"; do
      [ -e "$path" ] || changed+=("$path")
    done
  else
    changed=("${current[@]}")
    echo "AUTO_BASELINE=missing; using full worktree scope"
  fi
  printf '%s\n' "AUTO_CHANGED_FILES=${#changed[@]}"
  local social_hit=0 content_hit=0 security_hit=0 integration_hit=0 path
  for path in "${changed[@]}"; do
    case "$path" in
      app/services/social_*|app/services/content_social_*|app/routes/command_center.py|tests/kemet/test_social_*|tests/kemet/test_content_social_*) social_hit=1; content_hit=1 ;;
      app/services/content_*|app/templates/command_center.html|tests/kemet/test_content_*) content_hit=1 ;;
      app/core/execution/*|app/core/security_*|app/services/automation_approval_service.py|tests/kemet/test_security_*|tests/kemet/test_unified_approval_execution.py) security_hit=1 ;;
      app/services/commercial_*|app/services/revenue_*|app/services/social_measurement.py|tests/kemet/test_commercial_*|tests/kemet/test_revenue_*) integration_hit=1 ;;
    esac
  done
  if (( social_hit )); then echo "AUTO_GATE social"; social; fi
  if (( content_hit )); then echo "AUTO_GATE content"; content; fi
  if (( security_hit )); then echo "AUTO_GATE security"; security; fi
  if (( integration_hit )); then echo "AUTO_GATE integration"; integration; fi
  if (( !social_hit && !content_hit && !security_hit && !integration_hit )); then echo "AUTO_GATE fast_only"; fi
}

case "${1:-}" in
  auto) auto ;;
  snapshot) snapshot ;;
  fast) fast ;;
  social) fast; social ;;
  content) fast; content ;;
  security) fast; security ;;
  integration) fast; integration ;;
  smoke) smoke ;;
  release) release ;;
  full) full ;;
  *) usage ;;
esac

echo "VERIFICATION_PIPELINE_PASS profile=$1"

# End of verification pipeline


# Verification profiles are intentionally fail-closed.

