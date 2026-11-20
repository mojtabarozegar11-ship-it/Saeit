# MOJ PROP Simulation Isolation Gate

Scope: English-only mojplaywin.com/moj-prop/. This branch is review-only; it is not deployed and no live payment flag is changed.

## Purpose

The target database must be usable without the 16.67 GB factory database. Five tables provide the minimum independent state:

| Table | Responsibility | Cross-database dependency |
|---|---|---|
| prop_firm_propsimulationidentity | Opaque email/provider identity | None |
| prop_firm_propsimulationinvoiceowner | Binds a settled invoice reference to an identity | None; bounded immutable string |
| prop_firm_propsimulationaccount | Challenge and funded-account simulation compartments | Only isolated tables |
| prop_firm_propsimulationloginchallenge | One-time login/recovery challenge digests | Only simulation identity |
| prop_firm_propsimulationevent | Append-only simulation evidence and risk observations | Only simulation account |

## Non-negotiable invariants

1. No new model has a foreign key to auth_user, the factory database, or a shared user table.
2. Payment ownership is represented by an independently reconciled invoice reference; a browser-submitted transaction is never authority.
3. Both challenge and funded-account records are simulation records. Creating a funded simulation row does not authorize a live trade or payout.
4. Login challenges persist only a digest, never the one-time code.
5. Event identity is idempotent per account by event_ref and sequence_no.
6. Every write path must be restricted to a private reconciliation/service adapter; public HTTP cannot create settlement or event authority.
7. Target migration must be executed by a migration administrator, while the runtime user remains limited to SELECT/INSERT/UPDATE/DELETE.

## Release gates still closed

- independent capital proof: not evidenced
- jurisdiction approval: not evidenced
- broker contract: not evidenced
- merchant settlement readiness: not evidenced
- KYC/eligibility readiness: not evidenced
- owner canary: not evidenced
- English route connection: not implemented
- live invoice route: disabled

## Next implementation order

1. Review this schema and migration in CI.
2. Add a database router with fail-closed read/write rules.
3. Add private identity/login and payment-reconciliation adapters.
4. Run migration 0011_simulation_isolation only with the migration administrator.
5. Point only the English MOJ PROP runtime to the dedicated database.
6. Run a staging canary, then reassess release gates.
