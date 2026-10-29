# Offline V4 validation and transfer controls

- V4 expands V3 accounting-period protection to invoices and invoice payments, including protection against back-dating and editing frozen records.
- Payment on an old invoice in a **new open period** is not forbidden by the old invoice period, as expected by the payment journal pattern.
- Previous PHP period regression incorrectly attempted to change frozen journal lines after freezing; updated to assert that the write is blocked.
- Independent **read-only** Python reconciliation checks exact seeded two-line posting patterns for invoices and settlements, currency/date consistency, overpayment, negative stock, journal integrity and foreign keys, without any automatic repair. This is not a statutory accounting audit or bank reconciliation.
- The new tests do not cover all human operations, integrations, edge conditions, or corporate regulatory requirements.
- The PHP CLI on this container lacks PDO_SQLite. Unexecuted PHP behavioral suites must stay tagged NOT_RUN. A successful Python SQLite schema test is *not* equivalent to execution of PHP business paths.
- No live site, data or scheduling operations are included.

## Remaining release blockers

1. Execute all seven PHP PDO_SQLite behavior suites on an authorized CI runner, inspect logs and repair failures.
2. Reconcile source with live private cPanel modules and check binary/site-local dependencies.
3. Complete and test treasury, payroll, statutory accounting, official taxation, agriculture/lab/production, AI task execution and authenticated ChatGPT transport.
4. Verify real-data backup restore and owner-authenticated staging with role boundary checks.
5. Obtain project owner acceptance before **any** production release or scheduling.
