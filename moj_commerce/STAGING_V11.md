# MOJ Commerce v1.1 — staging PostgreSQL readiness (2026-10-21)

**Status: read-only infrastructure capability probe pending.** Based on the verified v1.0 cPanel synthetic Django tests: [112/112 successful](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39639414806).

## Scope
- Verified pinned GitHub Actions → VPS `githubops` → cPanel `zomorod2` SSH ProxyJump.
- Inspect available PostgreSQL binaries, VPS container runtime and free resources **without** connecting to existing databases, creating DBs, changing services, collecting secrets, or touching production paths.
- cPanel private stage root is `/home/zomorod2/Saeit-staging`; production `/home/zomorod2/Saeit` remains strictly read-only.
- Probe workflow: `.github/workflows/moj-commerce-v11-postgres-probe.yml`.

## After the probe
1. If cPanel supports a private stage-only PostgreSQL instance/role, use an independent database and proof of isolation.
2. Otherwise evaluate a bounded ephemeral PostgreSQL instance on VPS for **offline test only**, only if resources and configured permissions permit. An ephemeral GitHub CI PostgreSQL database does not count as a cPanel staging database.
3. Restore a synthetic backup into a distinct stage-only database and compare checksums and order/entitlement counts.
4. Run transaction concurrency, replay protection, and a synthetic checkout-to-delivery scenario.
5. Keep every real-money, scanner, public route, migration of Production, and external wallet function disabled.

Do not claim 100/100 production readiness from any of these synthetic tests.

## Execution receipt
Pending actual GitHub Actions run.