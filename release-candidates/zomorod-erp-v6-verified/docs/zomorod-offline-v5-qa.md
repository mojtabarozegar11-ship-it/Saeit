# Zomorod ERP — Offline V5 verification report

**Status:** Source-only engineering handoff, not a certified/production deployable ERP.

## New code and safeguards

- Added four SQLite insert/update triggers to reject reuse of one journal posting by two invoices, two payments or across invoice/payment families. Existing records are never modified; independent audits detect pre-existing conflicts.
- Extended read-only independent Python financial reconciliation with `posting_reuse` and `historical_negative_stock` alerts.
- Extended the PHP read-only finance report with the equivalent two alerts, using cursor-based O(n) historical inventory balance scanning.
- Updated synthetic PHP accounting-audit fixtures for the complete posting references and dated stock movements.
- Added a Python SQL integration suite which extracts the **actual** `CREATE TABLE` statements from `app.php` and the **actual** triggers from `period_controls.php`, then checks invoice postings, payments, historical-period locks and duplicate document references.
- Added 2 additional period SQLite tests, 3 additional independent finance cases and 5 real-schema integration cases.

## Verified

- 25 available offline checks passed locally, including PHP syntax checks and all applicable Python/SQLite test scripts.
- **13/13** financial invariant cases, **13/13** period SQLite cases and **5/5** real-schema SQL integration cases passed.
- GitHub Actions [run #40882571064](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40882571064) verified the **previous GitHub baseline** under PHP 8.2 and 8.3 with PDO_SQLite; it **did not** run this V5 package.
- **Seven PHP PDO_SQLite behavioural suites in this V5 package remain unexecuted** in the conversation workspace (local PHP has PDO but no PDO_SQLite). The bundle CI workflow is configured to run them under both 8.2 and 8.3 once these sources are transferred to the repository.

## Mandatory pre-production checks

1. Transfer and reconcile the V5 source with live server-only PHP extensions; never overwrite live `app.php` wholesale.
2. Run **all seven** actual PHP + PDO_SQLite behavioural suites on PHP 8.2 and 8.3 and fix test failures.
3. Test integration through the real owner login with role checks and CSRF protections in an isolated staging clone.
4. Verify period freeze on a copy of actual data and check historical duplicates before enabling triggers.
5. Verify a consistent database backup and actual restoration, plus access controls, secrets/permissions and audit retention.
6. Complete statutory taxation/payroll/treasury, operational farming/LIMS/MES, and private ChatGPT command-signing and agent execution. Those are not implemented end-to-end.
7. Owner must authorize production release and, separately, any recurring one-hour management task.

**Financial transfers, statutory declarations, real employee changes, signed contracts and public site changes:** none were performed by this package.
