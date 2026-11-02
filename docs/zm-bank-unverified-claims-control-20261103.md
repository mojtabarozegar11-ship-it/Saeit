# Zomorod Melal — pending bank-claim controls (2026-11-03)

## Verified production change

Scope: `zomorodmelal.ir/business/banking.php`, the private company accounting SQLite database, the read-only operations console, and command-center task bridge.

**Critical finding fixed:** the previous bank page accepted a manually typed reference and immediately inserted `journal_entries`, `journal_lines`, `invoice_payments` and `bank_payment_evidence`, marking the invoice settled without independent confirmation from the bank. This was a semantic and financial-control risk.

## Current controlled lifecycle

1. A logged-in active admin or accountant opens the bank receipt page using the existing business session. Requests require POST and CSRF.
2. The operator submits a **claim** with a bank subaccount (1011 Mellat / 1012 Shahr), existing IRR invoice, amount, date and external reference.
3. `bank_claims.php` validates authorized bank, unique reference, invoice currency, date and total available balance net of other pending claims while inside an immediate SQLite transaction.
4. The claim is stored solely in `bank_receipt_claims` as immutable `status='pending'` and generates a corresponding audit event. **No invoice payment, journal posting, bank transfer, settlement or delivery is performed.**
5. The existing command-center scanner sees pending IDs using a read-only connection and creates an **idempotent financial review task**. It does not display bank references or customer information in task details.
6. The owner operations view displays pending-claim counts separately from actual `invoice_payments` entries.

No mechanism currently marks a claim confirmed. A future bank-provider or separately verified reconciliation process must be built before posting a real payment to the ledger and granting goods access. Avoid treating an operator-typed transaction identifier as a bank confirmation. No future release is implied by the presence of this queue.

## Schema

`bank_receipt_claims(id, invoice_id, bank_account_id, amount, claimed_on, external_ref, status, created_by, created_at)` with foreign keys, `amount>0`, `status='pending'`, and unique `(bank_account_id, external_ref)`.

The pre-change, consistent accounting SQLite backup and the previous `banking.php` version are stored privately on the authorized host under `/home/zomorod2/.backups/zm-bank-claims-20261103/`. Never commit backing databases, customer references, bank identifiers or secrets.

## Verification

- Technical PHP syntax checks passed for the 4 edited/added business code files.
- 13 isolated, disposable SQLite/PHP checks passed, including prevention of settlement/ledger writes, duplicate reference, excessive amount, invalid currency and future dates. **No test purchase** or real bank event was submitted.
- Two invocations of the real, existing command scanner returned successful status with zero newly created tasks and no duplicates (no live pending claims existed).
- Live public store returned HTTP 200. Anonymous reads of bank, operations and customer inbox returned HTTP 403.
- Live accounting SQLite `PRAGMA quick_check=ok`, no foreign-key violation.
- After deployment, production counters: invoices 0, invoice payments 0, ledger journal entries 0, journal lines 0, pending claims 0.
- Login with real owner credentials, bank/provider callback verification, paid order fulfillment and end-to-end production acceptance are **not** proven.
- The Python HTTP acceptance suite was updated in GitHub to reflect pending-only claims. It has **not** been confirmed passing by a GitHub Actions run at the time of this report.

## Next mandatory actions

Connect an authenticated PSP/bank callback with signature/authentication, replay protection, amount/currency/order matching, atomic accounting posting, reconciliation statements, and independently verified fulfillment. Build an end-to-end paid order only after a real saleable product is approved, licensed and securely deliverable. The factory must remain single-product and shall not auto-publish unreviewed goods.
