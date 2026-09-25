# Agent-Only Runtime Integration

The standalone Agent-Only package is integrated into SAEIT at the control-plane boundary rather than copied wholesale.

## Integrated security contract

`ApprovalRequest -> owner decision -> short-lived scoped grant -> one-time atomic consumption -> AuditLog`

The grant is:
- bound to an existing approved `ApprovalRequest`;
- issued only by the designated owner;
- limited to 30–900 seconds;
- scoped to explicit action/target metadata;
- consumed atomically once;
- audited on issue and consumption.

The standalone package's external deployment, Telegram, filesystem grant store, and independent orchestration runtime are intentionally not imported into production as parallel control planes. SAEIT remains the canonical Django runtime and keeps its existing deny-by-default task governance.
