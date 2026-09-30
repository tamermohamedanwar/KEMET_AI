# Kemet Capability Center Contract

## Purpose
Discover and select Kemet capabilities from user intent without creating
a second runtime, agent, executor, approval system, or MCP layer.

## Canonical Flow
INTENT
→ CAPABILITY DISCOVERY
→ CAPABILITY SELECT
→ TOOL SELECT
→ PLAN
→ SIMULATE
→ HUMAN APPROVAL
→ CANONICAL EXECUTE
→ VERIFY
→ EVIDENCE
→ OUTCOME
→ LEARN
→ NEXT ACTION
→ REPLAY

## Capability Contract

Each capability MUST define:

- capability_id
- name
- description
- intent_patterns
- inputs
- outputs
- required_tools
- permissions
- risk_level
- cost
- execution_contract
- verification_contract
- evidence_contract

## First Capability

capability_id:
document_automation

Purpose:
Convert PDFs, images, invoices, and similar documents into structured
Excel, CSV, or JSON data.

Pipeline:
INGEST
→ EXTRACT
→ NORMALIZE
→ VALIDATE
→ HUMAN REVIEW
→ EXPORT
→ VERIFY
→ EVIDENCE

## Architectural Invariants

- One Kemet Runtime
- One Agent / Commander
- One Governance layer
- One Approval boundary
- One Execution loop
- No duplicate runtime
- No duplicate executor
- No MCP inside Kemet
- Human approval remains mandatory before external/influential execution
- Evidence and provenance remain canonical
- No fabricated customer, payment, publication, or profit evidence

## Non-Goals

Capability Center is NOT:
- a new agent
- a new runtime
- an MCP server
- a separate workflow engine
- a second tool registry
- a replacement for the existing Agent Foundation

It is the discovery and selection layer over existing Kemet capabilities.
