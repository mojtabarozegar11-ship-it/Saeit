# MOJ Commerce v1.1 — private staging backup/restore receipt (2026-10-21)

**Status: stage capability inspection and synthetic SQLite backup/restore verified. PostgreSQL staging is blocked by missing account authority. NOT production-ready.**

## Verified prior baseline
- v1.0: isolated Django synthetic tests 112/112 on cPanel: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39639414806
- v1.1: all three isolated MOJ Commerce GitHub CI jobs passed: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39642316135

## Operational verification
- Workflow: `.github/workflows/moj-commerce-v11-postgres-probe.yml`
- Passing execution: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39642316091
- SSH reachability verified over GitHub Actions → VPS relay → cPanel with pre-approved pinned host fingerprints. Production `/home/zomorod2/Saeit` only checked for existence, without writes.
- VPS reported no available Docker/Podman/PostgreSQL commands under the relay account.
- cPanel reported client utilities `psql`, `pg_dump`, `pg_restore`, and `createdb`, but no `initdb` or `pg_ctl`.
- Read-only cPanel UAPI PostgreSQL restriction query failed; passwordless PostgreSQL connection with the current account also failed. No alternate/production database credentials were accessed. No PostgreSQL database was created, read or modified.

## Synthetic backup/restore performed
- Verified script: `tools/moj_commerce_stage_backup_smoke.py`
- Exclusive destination: `/home/zomorod2/Saeit-staging/moj-commerce-v11-synthetic-restore/mc11-17ce1e2fad85`
- Stage execution markers:
  - `V11_SYNTHETIC_BACKUP_RESTORE_PASS`
  - `V11_SYNTHETIC_ORDERS=3 ENTITLEMENTS=1`
  - `V11_LOGICAL_SHA256=583eca7ac509b203cc6978f05cb78f269c88a72eddf1582bccf6aacda49c77dc`
  - `V11_SMOKE_SOURCE_SHA256=4024b4b260f0f2b3d01cc6db9fa7d23c50f1c708c34e85de41fc582652fce11d`
- Three **synthetic** orders and one **synthetic** entitlement were persisted to a new SQLite database, backed up using the SQLite online backup API, and restored into a separate new database. Data counts, PRAGMA integrity, and ordered logical SHA-256 digest agreed.
- These are SQLite results; they **do not** certify PostgreSQL backup/restore, production customer records, or payment settlement.
- No real-money operations, wallet broadcasts, payments, production migrations, live site publishing, or edits to existing production databases were performed.

## Boundary and next prerequisite
1. Stage-only PostgreSQL database and dedicated role must be provisioned by the authorized account/hosting administrator; access may be supplied through existing secure configuration (do not place passwords in GitHub code, logs or chat).
2. Verify strict isolation from production databases before any stage migration, data write, or restore.
3. Test a new PostgreSQL *synthetic-only* backup and restore into a second isolated stage database; repeat integrity checks and CI concurrency/replay tests.
4. Keep live release/payment functions disabled until separate explicit acceptance and evidence.

Do not claim 100/100 commercial or production readiness from synthetic verification.


## Additional stage resilience acceptance (2026-10-21)

- Latest passing stage execution: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39643861357
- Latest passing isolated delivery/locking test suite: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39643861355
- Fresh isolated destination: `/home/zomorod2/Saeit-staging/moj-commerce-v11-synthetic-restore/mc11-c5fe1bf6e1da`
- Verified script content SHA-256: `01187d7143d4e3f9778540ba48f791bb3174779e8e60a8828acb41552fa69cb9`
- The seed, untouched backup and restored synthetic SQLite database passed integrity and foreign-key verification. The logical receipt remained `583eca7ac509b203cc6978f05cb78f269c88a72eddf1582bccf6aacda49c77dc`.
- An intentionally modified **separate synthetic copy** produced a checksum mismatch: `V11_TAMPERED_DATA_HASH_MISMATCH_DETECTED`.
- A repeated execution pointing at the existing destination was explicitly rejected without overwrite: `V11_REPEAT_RUN_OVERWRITE_DENIED`; the workflow verified the refusal text, not merely a nonzero SSH status.
- PostgreSQL cPanel authorization remains unavailable (same `CPANEL_UAPI_POSTGRES_READONLY_CALL_FAILED` and `CPANEL_LOCAL_PG_ACCOUNT_AUTH_NOT_AVAILABLE` markers). No PostgreSQL restore or staging role provisioning performed.
- No live site, payment, production database, or wallet transaction was changed.

**Scope limit:** These are synthetic SQLite fail-closed tests, not a production recovery drill, real customer data attestation or 100/100 readiness.
