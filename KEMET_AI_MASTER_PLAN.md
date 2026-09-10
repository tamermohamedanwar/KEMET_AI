# KEMET AI MASTER PLAN

## Product Identity
- KEMET AI BOS — AI Business Operating System
- Kemet AI Unified Command Center
- Slogan: Don't use another AI tool. Run your business with Kemet.

## Strategic Principle
Build from Egypt, design for the world, and sell globally.
Kemet is not a collection of unrelated AI tools. It is one governed Business Operating System.

## The Eight Core Systems
1. Kemet AI Core — reasoning, planning, agents, memory, RAG, model routing, orchestration.
2. Kemet Autonomous Business Engine — Goal -> Plan -> Workflow -> Review -> Approval -> Execution -> Result -> Learning.
3. Kemet Business OS — CRM, sales, customers, support, marketing, finance, operations, documents, contracts, appointments, invoices.
4. Kemet Intelligence & Decision Engine — KPI -> Decision -> Priority -> Approval -> Execution -> Outcome.
5. Kemet World Intelligence — verified global knowledge, markets, companies, technology, GitHub, competitors, regulation and trends.
6. Kemet Money & Commerce — subscriptions, entitlements, usage, billing, payments, revenue analytics, pricing and marketplace.
7. Kemet Markets Intelligence — stocks, crypto, FX, commodities, macro, risk, portfolio and scenario analysis; analysis only unless explicitly approved.
8. Kemet Builder — generate, test, review and deploy business software from natural-language goals.

## Industry Strategy
Do not create dozens of isolated industry apps. Use one core and add high-value Industry Intelligence/Packs only when justified.
Priority domains: finance, real estate, retail, manufacturing, media, sports, entertainment, education, professional services and e-commerce.

## Global Intelligence Rule
Every important new technology, GitHub project, company move, market trend or business model must be evaluated before becoming part of Kemet.
Decision outcomes: BUILD, INTEGRATE, WATCH, or REJECT.
Do not add projects merely because they are popular or trendy.

## Five-Gate Filter
1. Global value
2. Revenue or cost impact
3. Real intelligence gain
4. Competitive moat
5. Integration with the Kemet platform

If an idea does not produce strong value, it does not enter the core roadmap.

## Governance
- Human approval before side-effecting actions.
- No autonomous external execution.
- Fail closed on authorization, entitlement and policy boundaries.
- Intelligence layers remain advisory/read-only unless an approved governed execution path is used.
- No MCP in Kemet architecture.

## Current Architecture Foundations
- Orchestrator and governed execution
- Playbook Engine
- Canonical Execution Runtime
- Action Registry
- Central Execution Gate
- Approval Service
- Capability Registry
- Capability Analytics
- Business Outcome Attribution
- Outcome Intelligence
- Outcome Priority
- Decision Lifecycle
- Decision Accountability
- Decision Learning
- Decision Intelligence
- Business Control Loop
- Business Feedback Loop
- Decision Review Queue
- CRM Pipeline Intelligence
- SaaS Control Plane
- Monetization Guard with fail-closed entitlement and usage checks
- Monetization Guard wired into automation execution
- Monetization Guard wired into BOS capability catalog, capability detail/plan, analytics and operate routes

## Monetization Direction
Centralize entitlement and monetization enforcement without bypassing existing governance.
Then strengthen subscription integrity, payment providers, revenue analytics, global packaging and production launch.

## Weekly Global Intelligence
Review authoritative global sources and high-signal open-source projects weekly.
Focus on what changes Kemet's product, architecture, economics, governance or competitive position.
Record sources, findings, decisions and recommended next actions.

## Benchmark Philosophy
Use global leaders as reference points, not templates to copy.
- ServiceNow: governed enterprise workflows, AI platform, control and orchestration.
- Salesforce: CRM, data, workflows, AI and governed business actions.
- Stripe: subscriptions, usage billing, entitlements and monetization infrastructure.
- High-signal open source: agent orchestration, browser/computer use, workflow automation and developer agents.

## One-Month Build Principle
Do not spend a month creating hundreds of small projects.
Spend the month making the eight core systems deep, reliable, governed, commercially useful and globally competitive.
Every new feature must strengthen the platform rather than create another island.

## Product North Star
A company should be able to enter Kemet and say what it wants to achieve, understand what Kemet recommends, review the plan, approve governed actions, execute safely, observe business outcomes, and continuously improve.

Kemet should feel like the operating system of the business, not another AI chat tool.

## Checkpoint Discipline
Update this file whenever a major architectural, product, market or roadmap decision is completed.
Keep the file usable as a handoff after closing the app or starting a new session.

## Subscription & Billing Integrity — Completed Foundation

- Added `app/services/subscription_state_service.py` as the authoritative read-only commercial state resolver.
- Active/trial/trialing subscriptions retain their paid plan.
- Inactive, canceled, suspended, past_due, unpaid, expired and unknown-status subscriptions fail closed to the free effective plan.
- Entitlement resolution now consumes the effective subscription state rather than trusting a stale paid plan.
- Preserved no-database-mutation and no-external-execution semantics.
- Added focused subscription-state and entitlement tests.
- Comprehensive Kemet test suite: **177 passed**.

The next implementation milestone is Payment Provider Abstraction.

## Strategic Product Direction — Global Platform

KEMET AI BOS is being built as a globally competitive Business Operating System, with the explicit ambition to become a leading platform in Egypt and the Arab world, while using global-grade architecture from day one.

### Language & Localization
- Arabic and English are first-class product languages from the beginning.
- Web UI must support RTL for Arabic and LTR for English.
- Language preference is user/account aware.
- UI, system messages, AI responses, notifications, billing and core user journeys must be localizable.
- Language is a presentation/localization layer; business logic remains shared.
- Architecture should allow additional languages later without rebuilding the core.

### Omnichannel Access
Kemet will expose the same core capabilities through multiple channels rather than creating separate products:
- Kemet Web / Unified Command Center
- WhatsApp Bot
- Telegram Bot
- Future native mobile application

WhatsApp and Telegram are channel adapters into the same Kemet Core, identity, tenant isolation, permissions, governance, intelligence and execution system. They must not contain independent business logic that diverges from the platform.

### Approval & Governance Across Channels
All channels inherit the same governance rules. Read-only intelligence may answer directly when authorized. Consequential actions remain subject to Kemet's existing review and human-approval flow. No channel may bypass the Central Execution boundary or approval requirements.

### Mobile Strategy
- First: make the responsive web application excellent on Android, iPhone, laptop and desktop.
- Later: build a native Kemet mobile app on top of the same APIs/Core rather than duplicating platform logic.
- Mobile app is intentionally sequenced after core, billing and omnichannel foundations are stable.

### Platform Principle
Kemet is one platform, not a collection of unrelated bots, websites and apps. The shared loop remains:
Understand -> Decide -> Review -> Approve -> Execute -> Measure -> Learn.

New capabilities must strengthen the global platform and pass the existing BUILD / INTEGRATE / WATCH / REJECT filter. Feature quantity is not the goal; business value, intelligence, defensibility, integration and measurable outcomes are.

### Strategic Priority
The implementation sequence remains:
1. Subscription & Billing Integrity
2. Payment Provider Abstraction
3. Revenue Intelligence
4. Global Packaging & Pricing
5. Production Readiness
6. Kemet World Intelligence
7. Kemet Builder
8. Multilingual + Omnichannel implementation (Web, WhatsApp, Telegram), with native mobile later

This direction is a durable checkpoint for resuming work after closing ChatGPT or Termux.

### Payment Provider Abstraction — Completed
- Added a provider-neutral payment contract in `app/services/payment_provider.py`.
- Added a registry for payment providers with explicit provider lookup and fail-closed unknown-provider handling.
- Added configured adapters for mock, Paymob, Fawry, Kashier and Stripe.
- Adapters are intentionally non-executing until provider-specific configuration is implemented.
- Existing Paymob payment flow remains intact in `payment_service.py`; this milestone establishes the migration boundary without breaking it.
- Added provider boundary tests covering registration, fail-closed behavior and unknown providers.
- Comprehensive Kemet test suite after this milestone: **180 passed**.

### Next Commercial Milestone
Payment Provider Production Adapters -> Revenue Intelligence -> Global Packaging & Pricing -> Production Readiness.


## Revenue Intelligence Milestone — 2026-09-10
- Added `app/services/revenue_intelligence_service.py` as a read-only SaaS revenue intelligence layer.
- MRR and ARR are derived from active subscription plans and authoritative plan pricing.
- ARPU is derived from MRR / active subscriptions.
- Plan mix and active/inactive subscription counts are exposed.
- Churn is calculated only when a previous-period active baseline is supplied; otherwise it remains null rather than being fabricated.
- Expansion MRR, contraction MRR, LTV, and CAC remain null until Kemet has reliable period-over-period and acquisition-cost data.
- Explicitly preserves advisory/read-only semantics: no database mutation, external execution, payment execution, or auto-execution.
- Focused Revenue Intelligence tests: 2 passed.
- Full Kemet suite after milestone: 182 passed.
- Next milestone: Global Packaging & Pricing, then production payment/revenue readiness.


## Milestone — Payment Provider Production Boundary v1
- Paymob now has an explicit provider adapter behind the provider-neutral payment contract.
- Missing Paymob configuration fails closed; no network/payment execution occurs through the adapter in that state.
- Existing `payment_service.py` remains the legacy execution path during controlled migration; no breaking rewrite was introduced.
- Fawry, Kashier, Stripe, and mock remain registered through non-executing configured adapters until provider-specific production contracts are implemented.
- Payment provider tests cover registration, fail-closed behavior, and unknown providers.

## Production Payment Readiness v1 — 2026-09-10
- Production readiness now validates payment mode explicitly.
- Mock mode is valid for development/testing only.
- Paymob live mode requires API key, secret key, public key, integration ID, and HMAC secret.
- Missing Paymob webhook HMAC configuration fails readiness closed.
- Existing Paymob callback validates HMAC, transaction/order identity, amount, currency, success, pending, refund, and void state before activation.
- No autonomous payment/refund execution was introduced.
- Full Kemet suite: **188 passed**.
- Governance remains approval-first for consequential financial actions.


## Milestone — Global Packaging & Pricing v1 (2026-09-10)
- Added `PackagingService` as the canonical commercial package catalog.
- Billing now consumes the packaging catalog rather than rebuilding plan metadata locally.
- Each package carries positioning, target segment, billing interval, usage unit, overage policy, price, limit, and contact-sales state.
- No prices were changed without a deliberate pricing decision; current configured USD prices remain authoritative.
- Overage is not enabled by implication; Enterprise remains contracted/custom.
- Packaging is read-only and does not execute payments or mutate subscriptions.
- Comprehensive Kemet suite passed: **186 passed**.

### Next build sequence
1. Production payment verification/webhook boundary.
2. Production readiness and observability.
3. Kemet World Intelligence.
4. Omnichannel Foundation: Arabic/English + Web/WhatsApp/Telegram.


## World Intelligence Source Registry v1 — 2026-09-10
- Added a read-only source registry with trust, tier, and category metadata.
- World Intelligence Pipeline now enriches normalized signals with source identity and trust metadata before verification/ranking.
- Unknown sources fail closed to low trust (`unverified`, trust 0.40).
- No database mutation, external execution, payment execution, or auto-execute is introduced.
- Baseline before this milestone: 195 tests passed.

## Omnichannel Foundation v1 — 2026-09-10

Added a shared Web/WhatsApp/Telegram channel normalization layer with Arabic/English detection, shared user/organization/conversation identity context, Core routing, and fail-safe human-approval governance. No external channel integration or autonomous execution is enabled yet.

Validation: 205 tests passed in tests/kemet after the foundation milestone.


## Omnichannel Gateway v1 — 2026-09-10
- Added channel-neutral `OmnichannelGateway` foundation for Web, WhatsApp, and Telegram.
- Normalizes inbound text into one canonical message contract with channel, language, tenant, user, conversation, metadata, and deterministic request identity.
- Arabic/English detection is centralized; channels do not own business logic.
- Routing targets the shared Kemet Core; no channel bypasses governance or execution boundaries.
- Response envelopes explicitly expose approval/execution state and remain fail-closed for external execution.
- Actual WhatsApp Business and Telegram network adapters remain a later integration stage after the foundation is stable.

## World Intelligence Trust Flow — 2026-09-10
- Source registry metadata (`source_key`, `source_trust`, `source_tier`) now survives World Intelligence pipeline output.
- Conflict detection is wired into the pipeline and flags materially different source trust for the same category/title as `review_required`.
- World Intelligence remains read-only/advisory with no autonomous execution.
