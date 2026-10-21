# MOJ Commerce v0.5 — private dashboards, scanner telemetry and recovery policy

**Status: source-only, DRAFT, no cron installation, no cPanel deployment, no wallet operations.**

## Implemented in this patch

- Seller-only dashboard (`GET /moj-commerce/merchants/<uuid>/dashboard/`): identity-enforced metrics for own seller, revenue from completed orders only, currently unpaid/expired orders, mismatches and unused previously signed receiving-address count. No buyer identity, txid, file key, wallet address or private signing data in browser response. Seller suspension remains visible only to its authorized owner.
- Superuser + staff-only scanner heartbeat dashboard (`GET /moj-commerce/operator/scanner-health/`): shows disabled/not-configured/never-run/running/stale/degraded/healthy with bounded counts of due orders, repeated failures and discrepancies. **Healthy means a recent successful scanner run, not a verified real-money transfer.**
- Durable `ScannerRun` audit record (DB migration 0004), including started, completion time, sanitized counts and coarse error code. Operation failure never stores exception text or customer PII.
- One exclusive **session-level PostgreSQL advisory lock** around the ENTIRE financial scanner job, so two cron jobs cannot race while independently scanning. No SQLite operational fallback, no automatic live scheduling. Failures leave purchase scan states for next due retry according to the bounded backoff introduced in v0.4.

## Acceptance and remaining blockers

- CI must prove seller A cannot see seller B, guests and unrelated staff cannot see financial health, and no leaked wallet/customer details; stale/failed/not-configured/disabled health must not be labeled healthy.
- PostgreSQL 16 must prove a second scanner fails to acquire the same advisory lock while the first holds it. Django migration must match the models (no untracked changes).
- Real cPanel Django site still inaccessible because remote device offline. No verified mapping to its live `mpw_commerce` models/order storage/downloads.
- No actual merchant address pool or real wallet signatures on users' devices, no production secrets, no automated RPC failover across independent providers, no real financial flows, no security audit, no validated restorable backup, no customer support/refund workflow, no live cron heartbeat.
- A real 24/7 operations guarantee is impossible to claim without installing approved schedules, monitoring, alerts and actual end-to-end payment evidence.

## Owner decision prior to a live release

Approval of exact financial routing, vetted merchant account, PostgreSQL migration and rollback, independent TRON RPC operation, private file handling and a low-value real payment test are separate explicit decisions. This pull request must remain draft.