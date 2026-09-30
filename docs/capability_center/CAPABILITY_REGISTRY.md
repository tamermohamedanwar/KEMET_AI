# Kemet Capability Registry

| capability_id | name | intent | inputs | outputs | risk | approval |
|---|---|---|---|---|---|---|
| document_automation | Document Automation | Convert documents into structured data | PDF, image, invoice, document | Excel, CSV, JSON | low | human review |

## Selection Rule

The Capability Center MUST select capabilities by user intent.

Example:

User intent:
"Turn these invoices into an Excel file."

Selected capability:
document_automation

Execution path:
INTENT
→ DISCOVER
→ SELECT
→ PLAN
→ SIMULATE
→ APPROVE
→ EXECUTE
→ VERIFY
→ EVIDENCE
→ OUTCOME

## Registry Rules

- One canonical capability registry.
- No duplicate capabilities.
- Existing Kemet services remain the implementation layer.
- Registry selection MUST NOT execute work.
- Execution remains inside the existing Kemet canonical runtime.
- Human approval remains mandatory where required by policy.
