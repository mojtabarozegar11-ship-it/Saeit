# MOJ Commerce v1.0 — private cPanel staging Django smoke (2026-10-21)

Status: **unverified pending actual Actions run**. The workflow must not claim success before its live job concludes.

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

Pending — append the actual Actions run URL and observed pass/fail markers after the run. Never mark 100/100 production readiness based only on source or synthetic tests.
