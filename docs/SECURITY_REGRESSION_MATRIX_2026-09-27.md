# Security Regression Matrix — 2026-09-27

Status: IMPLEMENTED / NEEDS PROVIDER-BY-PROVIDER EXECUTION
Scope: webhook/callback replay, idempotency, timestamp semantics.

## Matrix

| Provider | Verification | Replay | Idempotency | Timestamp semantics | Required regression cases |
|---|---|---|---|---|---|
| Paymob | HMAC + integration/order/transaction/amount/currency checks | Verify duplicate callback does not change a paid payment | Same transaction/order cannot create a second paid transition | Verify provider timestamp, if present/required by integration contract | bad HMAC, missing HMAC, duplicate callback, conflicting transaction/order, amount mismatch, currency mismatch, stale timestamp |
| Telegram | Secret-token verification | Same update must not create duplicate business event | External update/message identity must collapse duplicates | Telegram update timestamp semantics must be documented and tested where consumed | missing/wrong secret, same update twice, same message twice, stale/future update |
| Meta/WhatsApp | X-Hub-Signature-256 verification | Same webhook delivery must not duplicate work | External message/event identity must be unique per organization/channel | Provider event timestamp must be validated/handled consistently | bad signature, body mutation, duplicate delivery, duplicate message id, stale event |
| Salla | Connector webhook verification | Duplicate order/event must be harmless | Normalized event idempotency key must be organization-scoped | Event timestamp handling must be explicit | bad signature, duplicate event, same event with changed payload, stale event |
| Bosta | Connector webhook verification | Duplicate tracking notification must not duplicate execution | Current implementation derives event key from org/order/state/timestamp | Timestamp is currently part of event identity; validate whether provider timestamp is authoritative | bad signature, exact duplicate, repeated state, changed timestamp, stale event |

## Required assertions

1. **Fail closed:** invalid or missing signature/authentication returns an error and does not mutate business state.
2. **Replay safety:** delivering the exact same provider event twice produces one durable business effect.
3. **Payload binding:** reusing an idempotency key with materially different payload data is rejected rather than replayed.
4. **Tenant binding:** an event key or replay attempt cannot cross organization boundaries.
5. **Timestamp policy:** each provider has an explicit accepted timestamp field, clock-skew window, timezone rule, and stale-event behavior. If the provider does not sign/provide a usable timestamp, record that as N/A rather than inventing one.
6. **No fabricated semantics:** tests must reflect the provider contract and current implementation; they must not assume timestamp or replay guarantees that the provider does not supply.
7. **Observability:** rejected replay/signature/timestamp cases emit safe evidence without secrets or raw authorization material.

## Current evidence

- Paymob callback verification is implemented in `app/routes/main.py:381-501` and delegates HMAC verification to `app/services/paymob_webhook.py`.
- Salla and Meta/WhatsApp verification paths are present in `app/routes/salla_whatsapp_product.py`, `app/routes/salla_whatsapp_bot.py`, and `app/routes/bos_command.py`.
- Telegram uses `X-Telegram-Bot-Api-Secret-Token` verification in `app/routes/bos_command.py`.
- Bosta builds an organization-scoped event key from order/state/timestamp in `app/routes/bos_command.py:87-90`.
- Provider-by-provider timestamp behavior is not yet certified. This is intentionally a test-matrix gap, not a claim that every provider requires the same timestamp rule.

## Execution order

1. Run the matrix in clean Linux CI.
2. Add provider-specific tests only where the provider contract and current code establish the expected semantics.
3. Add database-backed duplicate-delivery tests for durable idempotency paths.
4. Record each provider as VERIFIED, NEEDS DEEPER TEST, or BLOCKED with evidence.

## Boundary

No new feature is introduced by this matrix. It is stabilization/security verification only.
