# Master Agent dual-instance deployment contract

Owner decision: **retain the existing Master Agent on the website host unchanged; create a complete independent copy on VPS 178.239.147.150.** This is a COPY, not a MOVE. Do not remove, overwrite, disable, or redirect the hosting instance.

## Preconditions
1. Locate the *actual deployed* Master Agent root, runtime process/service, dependencies, state and database on the hosting account. Do not assume the `master_agent/` repository directory is the deployed runtime.
2. Measure code + state + logs + media and VPS disk/RAM headroom. Capture file inventory and hashes without logging secrets.
3. Create a consistent, encrypted, restore-tested backup of the source. Exclude ephemeral caches but do not omit persistent state or attachments. Store backup outside both instances when feasible.
4. Confirm VPS Python/runtime compatibility, service user, network egress, firewall, database and secret injection. Provision fresh per-instance credentials. Never copy active production tokens blindly.
5. Preserve owner approval for all external side effects and deployments. No production cutover without a separate owner approval.

## Copy and isolation
- Host instance: preserve existing paths, process manager, environment and database.
- VPS instance: deploy into a separate dedicated directory and Unix user; isolate virtualenv, logs, queues, DB/schema, cache, locks, scheduled jobs, file storage and API credentials.
- Transfer the full identified application source, pinned dependencies, migration scripts, configuration *template*, and a consistent snapshot of required state. Validate SHA-256 manifest at destination.
- Never run both schedulers, outbound publishers, payment workers, or autonomous executors against the same live queue or credentials. Keep VPS outbound/automated jobs disabled until explicitly approved; initial boot is read-only/sandbox.
- For ongoing synchronization, use an explicit owner-approved direction and conflict policy; initial copy is a point-in-time snapshot, not automatic bidirectional sync.

## Acceptance gates
A. Hosting original remains online and functionally unchanged.
B. VPS file manifest matches snapshot; secrets are separate and private.
C. VPS app passes import/config checks, DB migrations on isolated DB, healthcheck, representative task, restart and recovery tests.
D. Resource usage fits 4 GB VPS with headroom and does not destabilize the factory.
E. Any independent outbound action requires the established owner-approval policy.
F. Document rollback: stop only VPS instance; original host stays untouched.

**Status:** architecture/contract only. Actual host inventory, snapshot, transfer, and VPS deployment have not yet been executed or verified.
