# Zomorod ERP — Offline V3 control and QA report

This package is a development snapshot with deterministic checksums, synthetic tests and offline financial safeguards. **It is not a certified ERP or a production-ready deployment.** No live data or credentials are distributed.

## Changes from V2

- Accounting period lock and dual-controller closure review in `content/zomorod-business/period_controls.php` using the **same accounting SQLite database** as journal postings.
- Independent two-person approval (requester cannot close their own period); journal balance verification by document and currency; SHA-256 fingerprint of the reviewed period.
- Database-enforced insert, update and delete guards against direct modifications to frozen months, including legacy code paths that bypass the UI's posting helper.
- Immutable review-event journal and fail-closed period transitions, including prohibition on reopening a finalized period.
- `record()` entry path now checks financial period state; backdated entries to a frozen period are rejected.
- Eight database schema/concurrency tests and a separate PHP behavioral regression suite.

## Testing scope

The Python sqlite3 tests execute the actual SQL DDL pulled out of the PHP module and test direct SQL operations, race conditions, forbidden updates and audit immutability. **They do not execute the PHP decision code.** PHP syntax checks execute locally. PHP behavioral tests require the `pdo_sqlite` extension. On the provided offline runtime that extension is not installed, so these tests are classified `NOT_RUN`, not `PASS`.

The archived CI workflow requires PHP 8.3 plus `pdo_sqlite`, `sqlite3` and `mbstring`. It will fail if the extension is absent and must explicitly verify all PHP suites before a release claim. Actual live owner and financial acceptance remain outstanding.

## Deployment restrictions

Never overwrite the active private `app.php` wholesale; live extensions were observed that differ from the repository baseline. A copy of this package must be staged after protecting and comparing the actual private source, making a recoverable database backup, testing a restoration, and confirming authenticated role access. **Do not execute `period_controls.php` against a company ledger directly** without reviewing its new tables and triggers in a disposable staging restore; installing triggers on a live ledger is a schema change. Do not activate any hourly schedule or public command endpoint.

To re-run tests without invalidating the distributed SHA-256 manifest, use `python3 scripts/run_all_offline_qa.py --report-out /tmp/zomorod-new-report.json`. Running without this flag overwrites the included QA report, which is intentionally detected as a file change by checksum verification.
