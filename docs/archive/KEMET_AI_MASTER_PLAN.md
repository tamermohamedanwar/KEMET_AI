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


## 2026-09-20 — Kemet Media OS / Unified Production Roadmap Lock

### Strategic product direction
- Kemet remains one governed AI-native Business Operating System; Media OS is a domain operating system inside Kemet, not a separate product/runtime.
- Canonical media identity: **Kemet Media OS**; specialized cinematic engine: **Kemet Cinema Engine**.
- Mission: “قل لـ Kemet ما الفيلم الذي تريد صنعه، وKemet يتولى هندسة الإنتاج كاملة.”
- Canonical production chain: Idea → Story → Script → World → Characters → Direction → Shots → Audio → Generation → Editing → QA → Repair → Final Artifact.
- Human remains the decision-maker; consequential external actions remain behind the Canonical Runtime and Human Approval.
- Kemet itself remains NON-MCP. Providers, open-source models, GitHub projects, and compute backends are replaceable capabilities, not Kemet architecture.

### Unified Command Surface
- Main page starts with one intent-first command field: user states what they want in natural language.
- Kemet infers production/business intent and dynamically presents the relevant action rail and visual choices.
- For media requests, show visual direction cards/previews such as Cinematic, Animation, Cartoon, Motion Graphics, Photoreal, Stylized, and Custom, then progressively reveal context-specific controls.
- Visual choices become explicit user decisions captured in canonical production state; prompts remain derived artifacts, never the source of truth.
- Avoid static legacy domain tabs and avoid forcing users to know production terminology.

### Kemet Media OS target layers
- Creative Intelligence, Production Intelligence, Production Memory, Continuity Intelligence.
- Cinematic Director Engine, FilmDSL, Storyboard/Previs, Character Identity, World Continuity.
- Voice/Audio Intelligence, Editorial Intelligence, Cinematic Render Pipeline, Cinematic QA.
- Critic → Repair → Targeted Regeneration, Capability Intelligence, Generation Routing, Compute Intelligence.
- Golden Reference System, Episode/Film Graph, provenance/evidence, governance and approval.

### Engineering roadmap
1. Integrate intent-first Command Surface with the existing BOS planning path; no parallel runtime or executor.
2. Replace the legacy static mode strip with a dynamic Action Rail and contextual visual-direction cards.
3. Extend canonical production-state contracts for visual direction, style, references, continuity, and user decisions.
4. Implement Media OS/Cinema Engine orchestration around the existing Media Factory and provider/capability fabric.
5. Establish Golden Reference + Character Identity + World Continuity as first-class production memory.
6. Build FilmDSL + Shot Director + Storyboard/Previs so production is engineered before generation.
7. Add generation routing and Compute Fabric so phone is the control surface while heavy work can run on PC/GPU/cloud/provider infrastructure.
8. Add semantic/cinematic QA and Critic → Repair → Targeted Regeneration; repair the smallest failed unit instead of regenerating everything.
9. Prove one reproducible end-to-end cinematic pilot through the governed pipeline.
10. Expand the same engine to advertising, animation, cartoon, motion graphics, educational video, branded films, series and shorts without creating separate generators.
11. Package the resulting capability into the broader Kemet commercial/control-loop architecture.
12. Run focused verification after each gate and a fresh full-suite regression before declaring release health.

### Non-negotiable architecture boundaries
- Preserve tenant isolation, billing/usage controls, evidence/provenance, idempotency, approval-first execution, and canonical execution governance.
- Do not convert Kemet into a bundle of GitHub projects; extract patterns and implement Kemet-native capabilities.
- Do not claim full-suite green from historical evidence; only fresh verification counts.
- Phone = Production Console/control surface; compute may be remote and dynamically selected.

### Immediate starting point
**Start with the Unified Command Surface:** redesign the existing Command Center beneath the intent field into the dynamic Action Rail + contextual Visual Direction selection, then wire the selection into canonical planning/production state without introducing a new runtime.


## 2026-09-20 — Dynamic Command Surface Gate Completed

The first engineering gate of the Unified Command Surface roadmap is now implemented. Kemet accepts natural-language intent, derives a contextual Action Rail, and for visual requests exposes selectable Visual Direction Cards. The selection is captured as canonical production state before downstream prompt derivation.

This follows current global interaction patterns around adaptive multimodal interfaces and creative systems that expose visual references, style control, consistency, and camera-oriented choices while preserving user agency. Provider-specific capabilities remain replaceable backends; Kemet owns the canonical state and governance.

Implementation boundary: existing Command Center planning route remains the planning boundary; no parallel runtime or executor was added; Kemet remains NON-MCP.

Verification gate: 24 focused tests passed. Full-suite status is intentionally unchanged and unclaimed.

Next implementation gate: Production State → Media OS production graph → Golden Reference → Character Identity → World Continuity → Shot Director → Golden Shot.


## 2026-09-20 — Kemet Production OS Naming Evolution
- Canonical production-layer name is now **Kemet Production OS**.
- **Kemet Cinema Engine** remains the specialized cinematic engine within it.
- **Kemet Media OS** is retained only as a legacy/internal compatibility term.
- No architectural rebuild follows from this naming change; all existing production contracts, graphs, governance, and provider abstraction remain canonical.
- New roadmap work and new documentation should use Kemet Production OS.


## 2026-09-20 — Production Intelligence Evolution
The next canonical layer above Kemet Production OS is Production Intelligence: persistent typed production state, production memory, structured production specification, dynamic task orchestration, evidence-driven critic/repair, and bounded policy evolution. This extends the existing architecture rather than replacing it.

Implementation sequence:
1. Production Intelligence contract and typed state.
2. Production Memory and trajectory evidence.
3. Kemet-native structured production specification (FilmDSL-inspired, provider-independent).
4. Dynamic task stack/orchestrator over the existing Production Graph.
5. Critic/Repair evidence loop with replay and QA.
6. Bounded learning/policy evolution with explicit validation and governance.
7. Integrate free-first compute discovery without weakening execution controls.

## 2026-09-21 — KEMET CONTINUE PROTOCOL / STABLE 100% PATH

This section supersedes any older continuation wording that could be interpreted as requiring Kemet to stop engineering and wait for Telegram activity. Kemet remains the primary project and the 100% end-state remains the fixed target. Telegram is a governed channel inside Kemet, not a separate project and not a reason to pause platform completion.

The permanent continuation command is KEMET CONTINUE PROTOCOL. It means: inspect the latest live/runtime truth and repository state; reconcile Constitution, Canonical Current State, Master Handoff, Project State and the 100% Master Completion Matrix; review current authoritative external sources when they materially affect the engineering decision; select the single highest-value dependency-aware closure path; bundle compatible implementation, verification, documentation and checkpoint work into one coherent pass; run focused verification and the appropriate regression level; update canonical state; and continue toward the next closure boundary.

The fixed product objective is Kemet 100%: Business Understanding -> Intelligence -> Plan -> Simulate -> Approve -> Execute -> Evidence -> Content/Production -> Distribution -> Audience -> Real Lead -> Qualification -> Offer -> Payment -> Fulfillment -> Revenue -> Cost/Profit -> Learning. No feature, channel, provider, media task or temporary blocker may replace this objective.

Telegram remains ready for real-world commercial proof and should be used when a genuine prospective customer is available, but Kemet engineering must not stop while waiting for a real lead. The engineering track and the real-world commercial-proof track proceed as one dependency-aware roadmap. No synthetic lead, payment, revenue, fulfillment, profit, publication or generation evidence may be created.

No new AI provider is to be introduced merely to change direction or because another provider exists. Provider-neutral internal contracts remain the architecture rule. The assistant may research current technical sources and compare documented practices, but recommendations must remain subordinate to Kemet's existing architecture and 100% closure criteria.

Media generation or modification remains prohibited unless the human explicitly says "اعمل فيديو". Production capability gaps may be analyzed and hardened without generating media.

Bundling rule: prefer one coherent implementation/verification batch over fragmented next-step prompts. Do not restart, redesign, duplicate architecture, create parallel executors, weaken governance, or silently change the end-state.

Decision rule: when several incomplete domains exist, choose the highest-value dependency closure that advances multiple downstream stages without violating a real-world boundary. When a real-world input is genuinely required, stop only at that boundary and state the exact human action required; otherwise continue engineering.

State authority remains: LIVE RUNTIME / LIVE DATABASE EVIDENCE -> Constitution -> Canonical Current State -> Master Handoff -> Project State -> 100% Master Completion Matrix -> historical documents. Historical records are preserved and must be labeled rather than silently treated as current truth.

## 2026-09-21 — CONTINUE AUDIT CHECKPOINT / 100% PATH RECONFIRMED

KEMET CONTINUE PROTOCOL was executed against the current repository. The dependency-aware audit confirms that the stable product direction is unchanged: Kemet remains the primary workstream and Telegram remains a governed channel inside Kemet, not a separate development track.

Current engineering evidence: the bundled core/business/content/commercial verification set passed 46/46. No application architecture was changed in this pass because the remaining core blockers are predominantly evidence/capability boundaries rather than a justified missing parallel feature.

The current highest-value engineering rule is therefore: close existing integrations and evidence boundaries before adding new architecture. In particular, do not mark Business OS, Workforce, Knowledge, Content, Distribution, Commercial, Revenue, Profit or Learning complete merely because their services and tests exist. Closure requires the runtime evidence and downstream handoff specified by the 100% matrix.

Current unresolved real-world/capability boundaries remain: first genuine commercial lead; first real approved offer; first real payment/fulfillment/revenue/profit cycle; verified real publication/measurement; real image-generation capability; verified commercial audio/TTS rights; verified AI-video compute; and real multi-shot cinematic QA/repair proof.

No synthetic evidence was created. No media was generated or modified. No new AI provider was introduced. No governance boundary was weakened.

Next CONTINUE pass must again inspect live truth first, then bundle the highest-value closure work that is safely executable without fabricating external evidence, while keeping the real commercial-proof path ready in parallel.

## 2026-09-22 — KEMET CONTINUE PROTOCOL / EDUCATION + WORLDS + MENDES INTEGRATION VERIFICATION

- Live-first runtime state remained healthy: `/api/health=200`, `/api/ready=200`, `/mcp=404` by design; repository HEAD remains `ab6ad8c5af75e343e9087b1a6b83bc6a2eb032f2` and Alembic head `e1f4b7c9d620`.
- The dependency-aware product-extension verification bundle completed **12 passed / 0 failed in 9.67s** across `test_education_content_pipeline.py`, `test_kemet_worlds_intelligence.py`, and `test_hikayat_mendes_story_pipeline.py`.
- This verifies the existing Education → Worlds/IP → Mendes/story integration contracts at focused-test level without creating a second content engine, parallel orchestrator, new provider, or synthetic commercial evidence.
- No customer, offer, payment, fulfillment, revenue, profit, publication, or generation evidence was fabricated.
- No video was generated or modified.
- Closure remains `IMPLEMENTED BUT INCOMPLETE` under the 100% matrix because production/core closure requires real runtime evidence and downstream business/outcome proof, not tests alone.
- Canonical direction remains bundled dependency-aware closure toward Kemet 100%, with the genuine commercial-proof track active in parallel and Lead #7 preserved as technical-test/non-commercial evidence.
