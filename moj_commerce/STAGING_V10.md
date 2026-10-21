# MOJ Commerce v1.0 — private cPanel staging Django smoke (2026-10-21)

Status: **verified: isolated Django tests passed on cPanel staging (synthetic in-memory database only)**. No deployment or live service.

## Authority and boundaries

- Based on the source-verified v0.9 transfer (GitHub Actions run 39634544768).
- GitHub Actions is a narrowly scoped SSH transport and test launcher, not a production release.
- Pinned VPS `githubops@178.239.147.150:22` and cPanel `zomorod2@zohal.pws-dns.net:1396` via ProxyJump, using separately validated host SHA-256 fingerprints.
- **Only permitted write root**: `/home/zomorod2/Saeit-staging/moj-commerce-v10-sandbox/mc10-<head-sha12>`.
- Forbidden: `/home/zomorod2/Saeit`, public webroots, live databases, migrations against production, Passenger configuration, Cron, wallet secrets, RPC transfers and payment enablement.
- Do not run `.github/workflows/staff-staging-release.yml`, which can activate Production.

## Executable acceptance gates

1. VPS and cPanel identities, fingerprints, private staging root, Python 3.11 and at least 256 MiB free disk.
2. Source and Django test files archived only from the reviewed repository HEAD; checks reject path traversal and unexpected Git file modes.
3. Test dependencies downloaded as binary wheels on the runner. No cPanel package-index connection is required.
4. New unique private staging folder receives two archives over pinned SSH; both SHA-256 digests must match before extraction.
5. A completely separate `.venv` is built **inside that private folder** using only transferred wheel files. Nothing is pip-installed into system or production Python.
6. Test commands run from that folder with a scrubbed environment (`env -i`), `moj_commerce.test_settings`, synthetic SQLite **in memory**, and `MOJ_COMMERCE_TEST_POSTGRES=0`. All payment/checkout/scanner/recovery switches remain off.
7. `makemigrations --check --dry-run`, then the nine existing isolated Django test modules covering merchants, wallet signatures, fake chain verification, checkout, digital delivery, monitoring and repair. If any command fails, the job fails closed.
8. Successful job must include `STAGING_ISOLATED_DJANGO_SMOKE_PASS`, immutable stage path, both archive SHA-256 values and `STAGING_NO_PRODUCTION_WRITE_NO_LIVE_PAYMENT_NO_PUBLIC_ROUTE`.

## What this does NOT prove

This is a genuine Django execution on cPanel staging hardware using an isolated **synthetic** database, not a working public checkout. It cannot prove independent PostgreSQL staging availability, live chain/RPC agreement, cPanel public routing, backups, commercial legal status or real-money fulfillment. The previously green GitHub CI PostgreSQL lock test is separate.

## Execution record

Verified [successful GitHub Actions run 39639414806](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39639414806), 21 Oct 2026:

- cPanel SSH via pinned ProxyJump: PASS.
- CloudLinux Python 3.11 interpreter found; isolated `.venv` and offline wheel installation: PASS.
- Migration consistency: `No changes detected in app 'moj_commerce'`.
- Django: **112 tests / 112 passed**, 107.155 seconds, no system-check issues.
- `STAGING_ISOLATED_DJANGO_SMOKE_PASS` present.
- Stage-only private root: `/home/zomorod2/Saeit-staging/moj-commerce-v10-sandbox/mc10-76476c84ee63`.
- Source archive SHA-256: `48a2efe66973af1e81273f6c2d7dd1aa71e8955c48da384be8cacf1ced9f76e0`.
- Offline wheelhouse SHA-256: `a9d74a271d368f402476a55cc6db0e78e1d1f55a708d6eecdc4016cbd84316ab`.
- `STAGING_NO_PRODUCTION_WRITE_NO_LIVE_PAYMENT_NO_PUBLIC_ROUTE` present.

Prior failed attempts were fail-closed: first identified system Python 3.9; second installed a private Python 3.11 environment but lacked source package `mpw_tron_pro`. Both packaging/runtime issues were corrected before the successful run. The earlier isolated unsuccessful sandboxes were not deleted.

**No production certification:** Independent stage PostgreSQL, backups/restore, 24/7 monitoring, live chain quorum, financial reconciliation and real-money buy-to-download validation remain separate release gates.

## 21 October follow-up: locked quote and emergency-stop staging rerun

- Requested source under test: [PR #817](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/817), including immutable invoice price delivery and removal of payable wallet details after the operator switches checkout off.
- This documentation update intentionally triggers the existing same-repository, owner-gated `moj-commerce-v10-staging-smoke.yml` pull-request workflow; it does not modify the SSH workflow or elevate permissions.
- Acceptance remains the same: **new SHA-scoped private cPanel staging sandbox**, offline Django regressions, no live routing, no production writes and no real funds.
- Passing GitHub CI alone must not be counted as passing this cPanel staging rerun. The new job's execution record and hashes must be checked separately.
