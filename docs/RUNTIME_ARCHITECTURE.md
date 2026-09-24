# Saeit — Runtime Architecture

## Execution boundary
1. User/CEO command enters the API or management interface.
2. Master Agent creates a task plan.
3. Sensitive or high/critical-risk actions are blocked behind an owner ApprovalRequest.
4. Research Runtime records sources, evidence, findings and reports with database lineage.
5. AuditLog records orchestration and approval decisions.

## Research integrity
The runtime is evidence-first: a finding can reference evidence, and a report is produced from project artifacts. External web/API retrieval must be supplied through explicit adapters; the core runtime does not invent sources.

## Deployment status
This repository is an implementation foundation. Production deployment to the shared cPanel/Python 3.11 host is intentionally separate and has not been performed.
