# Astra 2.0 — isolated 0049 Stage 4→5 evidence schema (2026-10-15)

## What exists now

The integration canary branch is based on the established Saeit factory/staging-reconciliation-20261008 Django source, which has all migrations through 0048. It contains 59 copied Astra V2 private research/product files from the original PR #101, with historical 0048 models/routes and commercial code initially preserved. This branch is private R&D review and is not a live deployment.

Added a new migration named 0049_astra_private_research_intake, which creates two research-only tables:

- core_factoryqueueitem — durable keyed discovery hypotheses with stage, digest and opaque research record. Its publication_allowed and market_demand_verified fields are constrained FALSE in SQL; commercial_quality_score must remain NULL.
- core_discoverysnapshot — source URL, exact content hash, timestamp and structured source record attached to one hypothesis. Duplicate identical source reference/version rows are blocked; independently_verified must remain FALSE because no independent attestation service or qualified human reviewer has been integrated.

The models match the optional pre-existing read-only Astra research evidence adapter. A source reference can be recorded without pretending it is genuine willingness to pay. The stage enum explicitly does not authorize an auto-build, public listing or payment event.

## Verified code acceptance

[Integrated 0049 CI run 38680775000](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38680775000) completed SUCCESS:
- Django system check reported no issues and makemigrations --check --dry-run reported no model drift.
- 163 independent Astra technical/regression tests passed.
- 10 separate database-backed safety/constraint tests passed.
- Original 0048 migration chain plus 0049 applied to clean disposable CI SQLite successfully.
- Schema-only 0049 reversed to 0048 on the same disposable database, confirming the two new tables were removed and all legacy 0048 business tables persisted; reapplying 0049 succeeded.

**Important:** The CI sample database was new and empty. This proves migration mechanics, not safety or performance on the 367 MiB original VPS database. No original VPS SQLite write, site deployment, payment or original factory cron modification has been performed by these changes.

## Real VPS prerequisites

[Original VPS schema audit](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38679612254): migration 0048, 209 Product records, 479 ResearchSource rows linked to Evidence, private Astra V2 has three QA-accepted builder families.

[Private runtime audit](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38681221140): default python3 is 3.8.2 but the existing isolated factory venv supports Python 3.11.17 at /home/githubops/factory-runtime/.venv/bin/python. No global interpreter change should be attempted.

[Capacity audit](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38681382566): the original factory SQLite occupies about 367 MiB and the private filesystem had more than 25 GiB free at inspection. Any copy rehearsal requires measured reserve and a temporary encrypted or access-restricted workspace, with source DB opened read-only and temporary data removed after testing.

A scoped SSH-backed GitHub workflow for backup-copy migration exists in this branch. It is a **rehearsal only**, not a production migration. Do not claim completion until its run reports success for the nonempty-copy migration, rollback, original row preservation, and safe cleanup.

## Unfinished integration

1. Reconcile provider-backed DiscoverySnapshot provenance, sources and independent demand/market evaluation (current models deliberately prohibit fabricated positive claims).
2. Implement reviewed evidence -> candidate brief -> builder capability match with idempotent versions, bounded retries, rollback and safe lease semantics, first within isolated development only.
3. Verify expertise/domain correctness, real user value, copyright, accessibility, support and truthful fair pricing for three independent original prototypes.
4. Complete a real 24-hour reliability observation before declaring continuous high-quality product manufacturing.
5. Only then consider a controlled original factory cutover and private-to-store handoff. Publishing and payments require separate valid safeguards and reconciled real settlement.

**Sales readiness remains 0 verified commercial products.** Successful technical migration and mathematical ZIP tests alone do not justify retail release or a claimed 90+/100 quality rating.
