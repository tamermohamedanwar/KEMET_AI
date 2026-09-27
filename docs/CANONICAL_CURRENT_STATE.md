# Kemet AI — Canonical Current State

**Status:** CURRENT / VERIFIED FOR SOURCE TREE
**Verification date:** 2026-09-27
**Authority:** live source tree + local runtime checks. Historical documents do not override this file.

## 1. Current system state
- Kemet AI remains a Flask application with the existing canonical execution/governance architecture.
- Production Flask debug is fail-safe disabled.
- Real environment files are removed from the source/deliverable tree; `.env.example` contains placeholders only.
- Test dependencies are declared in `requirements-dev.txt`.
- Security regression tests exist at `tests/kemet/test_security_hardening_regression.py`.
- Clean review packaging is reproducible through `ops/build_review_package.sh`.
- Local `/api/health` and `/api/ready` returned HTTP 200 during this verification.

## 2. Working components
- Flask application / WSGI path.
- Authentication and organization model.
- Governed execution/authorization path.
- Revenue/payment pipeline and Paymob callback verification.
- Channel webhooks for Telegram, Meta/WhatsApp, Salla, and Bosta.
- Google Sheets connector with tenant-scoped OAuth credential lifecycle.
- Document ingestion/upload path.

## 3. Integrations
- Google OAuth / Sheets
- Facebook OAuth
- Telegram
- Meta/WhatsApp
- Salla
- Bosta
- Paymob
- Remote worker / generation contracts

Secrets are runtime configuration only; this document intentionally contains no credentials.

## 4. Operation
1. Copy `.env.example` to a local `.env` only outside versioned/deliverable artifacts.
2. Install runtime dependencies with `python -m pip install -r requirements.txt`.
3. Install test dependencies with `python -m pip install -r requirements-dev.txt`.
4. Run locally with `python app.py` for development; use `wsgi.py`/a WSGI server for production.
5. Run tests with `pytest -q`.

## 5. Testing state
- Python `compileall` over `app`, `ops`, and `tests`: PASS on 2026-09-27.
- `git diff --check` on the remediation set: PASS.
- Full pytest remains environment-blocked on the current Android/Termux environment because `cryptography` cannot currently be installed into `.venv` successfully.
- CI is the authoritative clean Linux test environment once changes are pushed.

## 6. Known security risks / follow-ups
- Payment checkout token encryption-at-rest is implemented with `payments.client_secret_encrypted` and a new migration `f9c8e2a1b704`; existing plaintext is retained only as a backward-compatibility read path until the migration is applied, then cleared.
- Upload validation is extension-based after save and does not currently perform content/MIME magic-byte validation.
- The legacy `/admin/` dashboard was found to expose cross-organization user/chat counts and records; it is now organization-scoped with regression coverage. Other admin-named routes that use `login_required` remain under route-by-route review.
- Generic Google/Facebook login previously lacked OAuth `state`; a signed-session, one-time state check is now enforced for those login callbacks.
- Webhook verification is implemented for the reviewed providers; replay/idempotency and timestamp requirements should continue to be tested provider-by-provider.
- Alembic graph review: `f9c8e2a1b704` is the sole declared head and chains from `f2a7c9d1b430` after `e1f4b7c9d620`; local DB remains at `e1f4b7c9d620`, so the payment migration has not been applied.

## 7. Next action
1. Rotate/revoke external provider secrets outside the repository; this requires provider-side access and is not claimed complete here.
2. Run the strengthened CI on clean Linux; local Termux cannot certify the full suite because the environment has the cryptography installation limitation.
3. Execute `docs/SECURITY_REGRESSION_MATRIX_2026-09-27.md` provider-by-provider and record evidence for replay/idempotency/timestamp semantics.
4. Apply `f9c8e2a1b704` only after `KEMET_PAYMENT_ENCRYPTION_KEY` is injected into the runtime; current DB is still at `e1f4b7c9d620`.
5. Continue the tenant authorization sweep for the remaining admin-named routes and object lookups; the legacy `/admin/` cross-tenant dashboard exposure is fixed and covered by tests.
6. Only after stabilization and green CI/tests, plan refactors for the four large files.
7. No feature expansion during stabilization.

## 8. Latest targeted revenue-intelligence update — 2026-09-27
- Existing Lead Intelligence is now connected to the existing RevenueEngine decision layer through RevenueDecisionService.
- Revenue decisions can refresh canonical, tenant-bound, evidence-backed lead intelligence before the canonical RevenueEngine decision kernel runs.
- No parallel revenue engine, CRM, scraper, spam system, executor, runtime, or external dependency was introduced.
- The decision response carries lead-intelligence qualification, scoring, evidence digest, and governance metadata when refreshed.
- External execution remains disabled and human approval remains required for governed side effects.
- Regression coverage was added for the Lead Intelligence → RevenueEngine bridge.
- Changed Python files compile successfully; focused pytest could not start because the current Termux virtual environment has no pytest executable.
- Full pytest remains environment-blocked by the existing cryptography installation limitation.
- Detailed resume state: `docs/HANDOFF_2026-09-27_LEAD_INTELLIGENCE_REVENUE_BRIDGE.md`.

## 9. Document authority
This file is the single current-state reference. Other design/roadmap/security documents are supporting or historical material and must be labeled CURRENT, VERIFIED, HISTORICAL, SUPERSEDED, STALE, or BLOCKED before being treated as authoritative.
