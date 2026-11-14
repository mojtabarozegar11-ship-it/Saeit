# Native TRX — cross-provider idempotency and revenue evidence boundary

**2026-11-14 · Source branch only · Sole organizational bot: mojtaba.bot.ai**

## Business risk and root cause
- `PaymentWebhookEvent` has uniqueness on **(provider, event_id)**, not a TRON-mainnet-global transaction key.
- The new `_record_paid` currently checks historical event IDs and ledger references. That is valuable but an isolated **check-then-create** is not a shared atomic exclusion lock against a distinct concurrently running walletless provider.
- Old walletless receipts use `walletless:tron-mainnet:<txid>` credit references; new merchant invoices use `tron-mainnet:<txid>`. These are different strings and thus a `LedgerEntry.reference` unique constraint does NOT create cross-provider uniqueness.
- The full **legacy walletless writer** and effective cPanel MariaDB state are not proven in this source branch. Do not claim the risk has been eliminated, or that any real customer was harmed.

## Source fix delivered
The new gateway's check uses `PaymentWebhookEvent.objects.filter(event_id__iexact=proof["txid"])` and `LedgerEntry.objects.filter(reference__iendswith=":" + proof["txid"])` in the existing `transaction.atomic()` invoice-row-locked path. This prevents another historical duplicate caused solely by upper/lowercase event or reference differences. It is **not** proof against concurrent old-provider writers.

Additional Django database test methods were added to `tests/test_tron_gateway_commerce_integrity.py` for uppercase old-provider event and credit plus unrelated transaction; these require full Django/DB execution and are not reported as passed.

## Operational read-only duplicate scan
From an approved, verified effective application environment, an operator can run:

```sh
python manage.py tron_conflict_audit --limit 5000
```

The command reads bounded `PaymentWebhookEvent` finalized events and `LedgerEntry` TRON credit references. It outputs only counts, warning categories and pseudonymous short SHA-256 fingerprints under `TRON_CONFLICT_AUDIT=`. It never reads or prints buyer emails, raw txids, sender wallets or payment secrets; it never updates, pays, sends email or contacts any chain RPC.

- **No zero-risk inference:** `production_payment_safe` is always `false`.
- **Truncation:** If either relevant SQL row set exceeds the limit, `complete=false`; a clean partial view cannot pass `no_conflicts_in_bounded_snapshot`.
- **Finding types:** multiple finalized events, multiple credit references, cross-provider reuse, orphan event, orphan credit, unprocessed finalized event, malformed txid/reference.
- **Operational caution:** a clean *completed* historical scan is just a bounded historical consistency observation; it does not prevent a future concurrent settlement race.
- **Provenance:** verify the actual cPanel Passenger code path and MariaDB database identity before citing any real counts. No such runtime evidence was taken in this cycle.

## Source tests executed, distinct from integration
- 34/34 actual pure Python unittests on `core/tron_tx_conflict_audit.py` passed.
- 11/11 tests exercised the **exact Django command class AST** with bounded read-only fake QuerySets; 45/45 cumulative tests passed.
- Both locally executed new Python sources and the AST test source match their GitHub blobs byte-for-byte after code upload; Python compileall passed.
- 27/27 structural checks on fetched GitHub branch code passed.
- No Django, MariaDB, production TLS, SMTP, two-RPC receipt, real payment or revenue intake was run or validated. No CI run was triggered as part of the patch.

## Release blockers and actionable path
1. Find and inspect **actual** legacy walletless settlement writer and its scheduled process. Verify read-only the host source and all existing receipts; preserve paid/pending entitlements.
2. Make both old and new settlement writers participate in ONE shared DB-enforced unique canonical-mainnet-txid claim or an equivalent transactional coordination scheme, including historical backfill and exception handling. Do not merely rely on pre-write `exists()`.
3. Independently verify a simultaneous two-worker same-txid race against the exact production DB engine/schema, including rollback and zero double credit.
4. Run full Django checkout, invoice, payment, ledger and private fulfillment regressions; recheck migrations and rights metadata, accepted buyer email, payable product/quote and download.
5. Independently reconcile network-received TRX to merchant-owned wallet and the accounting entries. Owner separately approves deployment/canary after actual host and rollback proof.
6. Keep parent Draft #2299 and child #2303 unmerged and un-deployed pending those gates. No funds, live emails, wallet transfers or production mutations authorized by this document.

## Economic measurement
Successfully executed source/test work is **not collected revenue**. The amount of real received revenue and global project-completion percentage remain **UNKNOWN** until authoritative production evidence is obtained. The sole approved bot identity remains `mojtaba.bot.ai`.
