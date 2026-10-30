# Zomorod Melal ERP offline V7 — treasury and reconciliation

**Status:** Verified development source, not a production release or comprehensive statutory ERP.

## New: offline treasury and aging tool

The new `scripts/treasury_reconciliation.py` offers a read-only reconciliation of the basic ERP's bank account journals with a bank statement CSV supplied by an authorized operator. It also computes aged receivables and payables by currency, separated by sales and purchases.

Statement CSV schema, in order:

```csv
reference,date,currency,amount_minor
PAY-01,2026-10-20,IRR,2500
PAY-02,2026-10-22,IRR,-800
```

Amounts are **signed integer minor units**, not decimals. A positive amount means an increase in the bank asset account, negative a decrease. The exact reference is compared against the ledger's `doc_no`; the account code defaults to `1010` and must exist, be active, and be classified as an asset. No fuzzy auto-matching is performed. Rows must have one of IRR/USD/EUR/AED currencies. A reference duplicated in the same currency is rejected. Each ledger document/currency is reconciled separately; cross-currency netting is prohibited. Date differences over seven days are reported as exceptions, as are amounts that differ even where the global totals happen to agree. Statement rows dated later than `--as-of` fail closed; future ledger entries are excluded.

Illustrative offline invocation (with **privately retained** accounting and bank files; do not commit them):

```shell
python3 scripts/treasury_reconciliation.py /secure/management.sqlite3 /secure/bank-statement.csv --as-of 2026-10-30 --bank-code 1010
```

Exit status 0 means *strict reference matching succeeded for the supplied files*, 2 means exceptions need investigation, and 3 means inputs or accounting integrity did not pass validation. None represents independent bank authentication or a financial audit. The tool is **read-only**: it neither touches bookkeeping records nor makes an actual payment.

`aging` reports open balances using invoice dates and only payments made no later than the `--as-of` date. Aging buckets: not due, 1–30, 31–60, 61–90 and over 90 days. This does not forecast cashflows, enforce credit limits or validate invoices with a bank.

## Offline QA boundaries

- The new module has 29 deterministic Python/SQLite tests, including signed amounts, matching, aging, non-mutating snapshot, unmatched payments, future cutoffs, cross-currency segregation, duplicate and malformed CSV, invalid schema, excess payment, no-write permissions, and journal balancing.
- The complete package runner also validates existing Python/SQLite security, period controls, accounting invariants, industry database and private command bridge.
- The eight **PHP with PDO_SQLite** suites in V7 are only marked PASS if they actually execute in an environment with the extension enabled. Syntax checks alone are not sufficient.
- The entire V7 package must be mirrored to a dedicated GitHub branch, with a fresh PHP 8.2 and 8.3 CI run, **before** claiming it passed cross-runtime tests; tests of the older repository baseline do not validate V7.
- The GitHub `app.php` differs from the live private `app.php`. Never replace the entire live program: stage, compare unique hooks, take verifiable backup and prepare rollback.
- This is NOT a statutory payroll/tax module, banking connector, external authorization or fully autonomous master-agent system. No recurring agent has been activated.