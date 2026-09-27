# KEMET AI — PROJECT STATE

## Project Identity
Project: Kemet AI
Vision: Universal AI Business Operating System
Current UI Vision: Kemet AI Unified Command Center

## Core Principle
The user says what they want, not how to do it.

## Unified Command Center
One simple interface for:
- General AI
- AI Agents
- Automations
- CRM
- Customer Support
- Marketing
- Finance
- Analytics
- Knowledge / RAG
- Execution
- Approvals
- Settings

Requirements:
- Modern UI
- Mobile-first
- Desktop responsive
- Simple for normal users
- Technical complexity hidden
- Business status instead of technical internals

## Security Architecture
Kemet Bridge
→ Execution Plan
→ Approval
→ Authorization
→ Central Execution Gate
→ Execution

Security tests completed:
- PLAN_SECURITY=PASS
- APPROVAL=PASS
- AUTHORIZATION=PASS
- CENTRAL_GATE=PASS
- EXECUTION=PASS
- REPLAY_BLOCK=PASS
- TAMPER_BLOCK=PASS
- TOKEN_NOT_EXPOSED=PASS
- ATOMIC_CONSUME_LOCK=PASS
- SECRET_ROTATION=PASS

Runtime security:
- PLAN_APPROVAL=PASS
- CENTRAL_GATE_AUTHORIZATION=PASS
- FIRST_CONSUME=PASS
- REPLAY_BLOCK=PASS
- TAMPER_BLOCK=PASS

## Kemet Bridge
Agent:
agent/termux_agent.py
Port: 8765

Bridge:
agent/chatgpt_bridge.py
Port: 8770

Current execution commands:
- health
- test_health
- compile
- git_status

## Execution Center
Backend:
app/routes/execution_center.py

Frontend:
app/templates/execution_center.html

Current architecture:
- Authenticated users can request execution plans.
- Admin approval required for execution.
- Authorization is generated server-side.
- Central execution gate validates authorization.
- Authorization is one-time.
- Tampered plans are blocked.
- Execution is proxied through the Bridge.
- Secrets are not exposed to the frontend.

## UI Access
General AI:
 /chat

Execution Center:
 /execution-center

Admin Bridge:
 /admin/bridge

Bridge UI is hidden from non-admin users.

## Product Modules
- AI Command Center
- Automation Studio
- AI Agents
- CRM
- Sales
- Customer Support
- Marketing
- Finance
- Construction
- Analytics
- Knowledge Base / RAG
- WhatsApp / Omnichannel
- Billing
- Marketplace
- Developer / Integrations
- Governance / Audit

## Existing Platform
Stack:
- Flask
- Flask-Login
- Flask-SQLAlchemy
- Flask-WTF
- Flask-Migrate
- Gunicorn

AI:
- OpenRouter
- FREE model strategy
- No Gemini

Databases:
- supportai.db
- instance/rag.db

## Existing Features
- Authentication
- Support Dashboard
- Ticketing
- AI Suggestions
- Analytics
- RAG/File Upload
- Automation Engine
- CRM foundation
- Billing foundation
- Pricing
- AI usage limits
- Execution security
- Kemet Bridge

## Pricing
starter: 9 EGP
business: 29 EGP
enterprise: 79 EGP

## Usage Limits
free: 100
starter: 1000
business: 5000
enterprise: 50000

## Current Development Direction
DO NOT build disconnected features.

Everything must converge into:
Kemet AI Unified Command Center.

Priority:
1. Unified modern UI
2. Mobile + desktop responsive design
3. Simple user experience
4. Connect existing modules to the Command Center
5. Hide technical infrastructure
6. Strong RBAC
7. Auditability
8. Safe execution
9. Monetization
10. Enterprise readiness

## Important Rule
Do not claim a test is PASS unless it was actually executed.

## Resume Keyword
When continuing this project, say:

"Continue Kemet AI Unified Command Center."

