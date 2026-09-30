#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
printf '%s\n' 'KEMET RELEASE READINESS GATE v1'
printf '%s\n' '== repository state =='
git status --short --branch
git diff --check
printf '%s\n' '== syntax =='
.venv/bin/python -m compileall -q app tests
printf '%s\n' 'PASS compileall'
printf '%s\n' '== focused readiness =='
.venv/bin/python -m pytest -q tests/kemet/test_production_readiness.py
printf '%s\n' 'PASS production readiness tests'
printf '%s\n' '== security boundary regression =='
.venv/bin/python -m pytest -q tests/kemet/test_governed_http.py tests/kemet/test_secret_boundary_regression.py tests/kemet/test_security_controls.py tests/kemet/test_security_baseline.py
printf '%s\n' 'PASS security boundary regression'
printf '%s\n' '== repository hygiene =='
git diff --check
printf '%s\n' 'PASS diff check'
printf '%s\n' 'RELEASE READINESS GATE PASSED'
