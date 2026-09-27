# Kemet AI — Security Follow-up Audit

**Date:** 2026-09-27
**Scope:** webhook signatures, OAuth state, payment callbacks, uploads, admin authorization, organization authorization, token storage, logging.

## Findings

### Webhooks/signatures — IMPLEMENTED / NEEDS MATRIX TESTS
- Paymob callback verifies HMAC, integration ID, order/transaction identity, amount, currency, and duplicate paid state in `app/routes/main.py:379-501`.
- Telegram, Meta/WhatsApp, Salla, and Bosta webhook verification paths were located in their route/service modules.
- Provider-by-provider replay/idempotency and timestamp semantics still need explicit regression coverage.

### OAuth state — FIXED FOR GENERIC SOCIAL LOGIN
- Google Sheets uses `SocialOAuthLifecycle` with a 600-second, hashed, one-time state bound to organization/user/channel at `app/core/social_oauth_lifecycle.py:13-47`.
- Generic Google/Facebook login previously omitted `state`. This was corrected using a signed-session, one-time, 600-second state in `app/routes/auth.py` and provider URL builders in `app/services/social_auth_service.py`.

### Payment callbacks — STRONG VERIFICATION, STORAGE FOLLOW-UP
- Callback verification is present and fail-closed for missing/invalid HMAC and integration mismatch.
- Amount/currency/provider/order/transaction checks are present.
- Payment checkout token storage is now remediated in source: `payments.client_secret_encrypted` uses a dedicated Fernet key, writes use encrypted storage, and migration `f9c8e2a1b704` encrypts existing plaintext then clears the legacy column. The runtime must be configured with `KEMET_PAYMENT_ENCRYPTION_KEY` before migrating rows.

### Uploads — PARTIALLY HARDENED
- Login and organization assignment are required at `app/routes/upload.py:14-41`.
- 25 MB size limit and an explicit extension allowlist exist at `app/services/document_ingestion.py:11-15,39-50`.
- `secure_filename` and symlink checks are present.
- Remaining gap: no content-signature/MIME magic-byte validation before ingestion. Treat as a follow-up hardening item, not a reason to redesign the ingestion pipeline.

### Admin routes — MIXED
- `admin_required` enforces login + `current_user.role == "admin"` in `app/admin/decorators.py:7-14`.
- `admin_bridge` and `admin_support` use `admin_required`.
- `admin_billing` and `admin_revenue` were tightened in this pass to use `admin_required`.
- Other `admin_*` modules still use only `login_required`; each route needs a route-by-route authorization decision rather than a blanket rewrite.

### Organization authorization — MOSTLY SCOPED, CONTINUE AUDIT
- User records and major business models carry `organization_id`.
- Revenue dashboard and the corrected billing summaries are organization-scoped.
- API keys bind to organization IDs in `app/services/api_key_service.py:12-53`.
- Continue checking every object lookup with an attacker-controlled numeric ID for an explicit organization predicate.

### Token storage/encryption — MIXED
- API keys are stored hashed, not as raw keys, in `app/services/api_key_service.py:12-23`.
- Tenant social credentials use Fernet-backed encrypted storage through `app/core/secret_boundary.py:51-79`.
- Payment checkout token persistence is now encrypted-at-rest in source; deployment remains blocked until `KEMET_PAYMENT_ENCRYPTION_KEY` is injected and migration `f9c8e2a1b704` is applied to the live database.

### Logs/sensitive data — NO CONFIRMED DIRECT LEAK FOUND IN TARGETED STATIC SEARCH
- Targeted logger/print search did not identify an obvious direct log of authorization headers, API keys, passwords, or credentials.
- Continue using the existing redaction boundary and add regression tests for representative secret-shaped values.

## Priority order
1. Rotate/revoke previously exposed external secrets.
2. Run clean Linux CI and the full test suite.
3. Add regression tests for the findings above.
4. Inject `KEMET_PAYMENT_ENCRYPTION_KEY` through runtime secrets and apply migration `f9c8e2a1b704`; do not edit old migrations.
5. Continue object-level tenant authorization review.
