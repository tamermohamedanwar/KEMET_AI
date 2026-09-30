# KEMET Security Baseline - ACTIVE_SUPPORT
Human approval is mandatory for production.
Tenant and identity binding enforced for every organization_id.
One-time execution authorization via execution_key.
Execution envelope validates approved_execution and authorization.
post-validation, and rollback on failure is required.
Rate limiting per tenant and per channel.
