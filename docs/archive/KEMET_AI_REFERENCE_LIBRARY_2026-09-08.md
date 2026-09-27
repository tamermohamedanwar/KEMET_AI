# KEMET AI — REFERENCE LIBRARY

Date: 2026-09-08
Status: ACTIVE PROJECT STANDARD

## Purpose

This library defines how Kemet AI uses external projects, repositories,
frameworks, APIs, research, and product references.

External references are benchmarks and sources of ideas.
They are NOT mandatory dependencies and are NOT automatically copied into Kemet.

## Kemet Best-in-Class Research Rule

There is no permanent "base" framework, repository, vendor, or technology.

For every strategic milestone, Kemet AI should search for the best
available solutions at that time.

The process is:

Discover
→ Compare
→ Evaluate
→ Select the best available approach
→ Adapt to Kemet architecture
→ Security / Governance review
→ Implement
→ Test
→ Measure
→ Keep, improve, replace, or remove

A newly discovered project may replace an existing reference if it is
demonstrably better for the specific Kemet requirement.

GitHub stars alone must never determine technical selection.

## Evaluation Criteria

References should be evaluated using:

- Architecture quality
- Production maturity
- Reliability
- Security
- Scalability
- Agent capabilities
- Orchestration
- Automation
- Integrations
- Developer experience
- User experience
- Observability
- Testing and evaluation
- Performance
- Cost
- Licensing
- Ecosystem
- Maintainability
- Future trajectory
- Fit with Kemet AI
- Business value

## Reference Categories

### Agent Intelligence

Potential references include:

- LangGraph
- OpenAI Agents SDK
- CrewAI
- Other superior agent frameworks discovered later

### Automation

Potential references include:

- n8n
- Dify
- Other superior workflow systems discovered later

### Integration / Tool Layer

Potential references include:

- MCP
- Public API ecosystems
- Webhooks
- Event-driven architectures

### Business OS / CRM

Potential references include:

- Comp AI CRM
- Orbiteus
- FusionClaw
- Other superior business operating systems discovered later

### Business Intelligence

Research areas include:

- KPI intelligence
- Revenue intelligence
- Forecasting
- ROI measurement
- Anomaly detection
- Decision intelligence
- Business intelligence graphs

### Governance / Security

Research areas include:

- Policy engines
- Approval systems
- Authorization
- Auditability
- Guardrails
- Sandboxing
- Tenant isolation
- Least privilege
- Secrets management
- Execution boundaries
- Agent governance

### Reliability / Evaluation

Research areas include:

- Agent evaluation
- Regression testing
- Observability
- Tracing
- Failure recovery
- Idempotency
- Cost measurement
- Latency measurement
- Outcome measurement

### Product / UX

Research areas include:

- AI command centers
- Agent dashboards
- Approval centers
- Workflow builders
- Business operating systems
- Mobile-first interfaces
- Unified business experiences

### SaaS / Monetization

Research areas include:

- Subscription billing
- Usage metering
- Agent usage billing
- Automation-run billing
- Integrations
- Marketplace economics
- Enterprise controls
- Agency models

## Confirmed External Reference

### Public APIs

Canonical repository:

https://github.com/public-apis/public-apis

Purpose:

A large curated catalog of publicly available APIs.

Usage rule:

Public APIs is a discovery/reference source.

Individual APIs must be evaluated independently for:

- Authentication
- License
- Terms of service
- Reliability
- Rate limits
- Privacy
- Security
- Cost
- Availability
- Production suitability

Do not automatically integrate every API listed there.

## Reference Usage Rules

1. Never copy secrets, credentials, tokens, or private data.
2. Never blindly copy an external architecture.
3. Never add a dependency solely because a reference uses it.
4. Prefer Kemet's existing infrastructure when it is sufficient.
5. Preserve Kemet's canonical governance and execution path.
6. Do not create parallel security or governance systems unnecessarily.
7. External references may influence architecture, UX, integrations, and product strategy.
8. Current official sources should be checked when technical behavior matters.
9. Use approximately 2–4 highly relevant references per major milestone.
10. Measure the result after implementation.
11. Replace references when better alternatives become available.
12. Kemet's security, governance, reliability, and business requirements override convenience.

## Kemet Canonical Execution Principle

Intent
→ Plan
→ Risk / Policy
→ Approval
→ Authorization
→ Central Execution Gate
→ Canonical Runtime
→ Action
→ Audit
→ ROI / Business Outcome

External references must fit this model rather than bypass it.

## Milestone Research Workflow

For each major milestone:

1. Identify the engineering/product category.
2. Search globally for strong current references.
3. Compare multiple candidates.
4. Select the strongest relevant approaches.
5. Inspect official documentation/repositories.
6. Extract patterns rather than blindly copying implementations.
7. Compare with existing Kemet architecture.
8. Reuse existing Kemet infrastructure where possible.
9. Implement the smallest production-oriented increment.
10. Run targeted tests.
11. Measure reliability, cost, latency, and business outcome.
12. Update this Reference Library and the Master Handoff.

## Current Kemet Priority

Immediate milestone:

GOVERNANCE INTEGRATION

Then:

Production-oriented Revenue Autopilot Agent

Then:

Universal Automation Planner

Then:

Automation Graph + Multi-Agent Business Operations

Then:

Universal Integration Layer

Then:

Marketplace + SaaS + Enterprise

## Permanent Rule

Kemet AI is not required to follow any single external project.

The objective is to continuously identify, evaluate, and combine the
best available engineering and product ideas while maintaining Kemet's
own architecture, security, governance, identity, business model,
and product vision.

END OF REFERENCE LIBRARY
