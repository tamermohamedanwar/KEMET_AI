#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
printf '%s\n' 'KEMET SECURITY EVIDENCE GATE v2'
printf '%s\n' '== security evidence regression =='
.venv/bin/python -m pytest -q \
  tests/kemet/test_security_events.py \
  tests/kemet/test_security_controls.py \
  tests/kemet/test_governed_http.py \
  tests/kemet/test_memory_security_boundary.py \
  tests/kemet/test_skill_admission.py \
  tests/kemet/test_admin_privilege_boundary.py \
  tests/kemet/test_untrusted_content.py \
  tests/kemet/test_automation_control_plane.py \
  tests/kemet/test_strix_security_testing_capability.py \
  tests/kemet/test_strix_security_evidence_service.py \
  tests/kemet/test_security_validation_gate.py
printf '%s\n' 'PASS security evidence regression'
printf '%s\n' '== syntax =='
.venv/bin/python -m compileall -q app tests
printf '%s\n' 'PASS compileall'
printf '%s\n' '== repository hygiene =='
git diff --check
printf '%s\n' 'PASS diff check'
printf '%s\n' 'SECURITY EVIDENCE GATE PASSED'
