# زمرد ملل — V6 Verified offline tests (29 October 2026)

**Scope:** V6 development bundle, not live production. No real business records, bank transfers, SSH secrets or recurring tasks are used. The production company website is unchanged.

## Confirmed regression execution

The *exact extracted V6 source* was executed with PHP **8.4.24** and compatible `pdo_sqlite` and `sqlite3` modules compiled for PHP extension API **20240924**, obtained from the repository's own isolated GitHub Actions workflow run **40931778408**. The retrieved extension binaries passed the source artifact's SHA256 checks before loading. The source package contains no extension binaries or credentials.

- **37 of 37** defined runner checks PASSED (PHP lint, independent Python SQLite/control tests, HMAC test and eight PHP PDO_SQLite behavioral suites plus authenticated synthetic web flow).
- Previously failing PHP period closure test: added the `posted_entry` / `entry_id` columns required by the changed accounting triggers, using explicit-column INSERTs in its synthetic fixture. No production schema was changed.
- Previously skipped web-flow integration test: included it in the runner, and supplied all newly required private PHP modules to its synthetic temp directory.
- The runner's `full_offline_database_tests_verified=true` means *only* that these defined suites passed with a working PDO_SQLite engine. It does **not** mean full ERP 100% implementation, statutory compliance, or readiness for cPanel production.

Run from extracted package with an independently configured PHP+PDO_SQLite (version 8.2/8.3/8.4 subject to compatibility):

```bash
python3 scripts/run_all_offline_qa.py --report-out /tmp/zomorod-offline-report.json
```

Do not write report output into the extracted source tree when comparing against manifest SHA-256 entries. On the verifier's machine, both ZIP and TAR.GZ must be validated using `python3 scripts/verify_erp_bundle.py ...`.

## Important unverified items

- V6 full suite has been executed here using PHP 8.4, **not** against the live PHP/cPanel runtime.
- Running the **same V6 package** on PHP 8.2 and 8.3 in GitHub Actions remains unverified until V6 sources are safely synchronized to the repo. Earlier 8.2/8.3 success applies to older baseline and payroll branches, not the combined V6 source.
- Full legal payroll, tax, statutory financial reporting, inventory valuation, laboratory accreditation, LIMS/MES, reliable external master-agent command bridge, role/accessibility/performance coverage and true disaster recovery are not complete.
- Never overwrite live `app.php`; cPanel contains private-only extensions absent in this repository.
- No public release, no recurring automation, no bank execution.
