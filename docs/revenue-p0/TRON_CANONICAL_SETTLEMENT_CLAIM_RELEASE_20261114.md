# TRON canonical claim — source implementation and production release barrier

**2026-11-14 · Sole organizational bot: `mojtaba.bot.ai` · Status: SOURCE-ONLY / NOT PRODUCTION READY**

## Business defect
The pre-existing new TRON gateway locked individual invoice rows, checked existing finality events and ledger credits, then wrote receipts. The old walletless provider was not proven to share that invoice lock or any global on-chain transaction unique key; distinct event providers and ledger reference prefixes can permit simultaneous same-TXID credit when writers race. **No actual duplicate customer charge or lost revenue is alleged.**

## Implemented: new-writer durable canonical claim
- New `core.TronMainnetSettlementClaim` uses a canonical lowercase 64-character mainnet TXID **primary key**, protected one-to-one references to the exact paid invoice and PaymentIntent, and a proof digest.
- Schema is declared in `core/migrations/0042_tronmainnetsettlementclaim.py` (dependency `0041_trongatewayinvoice`). **No production migration was run.** Concurrent draft branches can have migration graph conflicts; actual host migration history must be reconciled first.
- `canonical_settlement_claim` rejects malformed hashes, nonlowercase proof digest, bad sender, nonpositive block height/time, non-solidified proof and invalid input types. This pure validation does **not independently verify the blockchain**; the existing dual finalized-node `verify_native_trx` remains mandatory.
- In `_record_paid`, the claim is inserted *within the same transaction.atomic* after the existing legacy event/ledger checks and before the new event, credit, invoice, intent and order updates. A collision raises `IntegrityError` and unwinds the entire new invoice credit; no second credit is knowingly created through this participating writer. Replayed paid invoices require a matching claim.
- Buyer digital delivery and `tron_revenue_audit` now also require an exact matching claim; an invoice status of paid alone cannot authorize fulfillment or count as evidenced received native TRX.

## Crucial legacy-writer safety condition
The full deployed legacy walletless settlement writer is **not present in the fetched source tree**; references to `services.mpw_walletless_commercial_intent` and `services.mpw_trx_walletless_core` exist, but source files were not available from this branch. The new claim cannot control a **legacy writer which does not use it**.

For this reason `TRON_UNIFIED_SETTLEMENT_EXCLUSIVE_CONFIRMED` defaults to **false**. Until independent operational evidence establishes an exclusive single writer or a migrated shared-claim old writer:
- New `_new_invoice` / checkout / catalogue refuse payable new orders.
- Existing `invoice_page` can still display paid receipts, while hiding unpaid wallet destination and amount and refusing verification POST. No paid digital entitlement is inferred merely from that view.
- `tron_discover` and `tron_reconcile` short-circuit **before** calling chain RPC or writing an order when the flag is false.
- `_record_paid` also independently refuses credit, preventing a direct/internal call bypass.

**Do not set the flag to true on a real host solely because the code or the tests pass.** A false assertion of legacy isolation could double-credit across a non-participating writer.

## Executed quality assurance, exact source provenance
- 26/26 portable policy/SQLite integrity tests and 7/7 SQLite *two-connection* uniqueness/rollback tests ran successfully: **33/33 offline PASS**, Python compileall success.
- Actual portable policy/test/race-file Git blob SHA IDs were compared to fetched GitHub files after commit.
- 51/51 separate GitHub-fetched structural source checks succeeded across 14 relevant files. These are code checks, **not** runtime deployment acceptance.
- Eight additional Django ORM test methods were added for default denial, claim uniqueness, idempotence, malformed finalized proof, rollback and unrelated transactions. These were **authored/read back, not run**: Django is not installed in the local environment and the effective MariaDB is not connected.
- The SQLite race exercises two independent local connections with a shared primary key. An adversarial test deliberately shows that an old writer bypassing the claim can still credit. SQLite evidence is **not** a substitute for real MariaDB concurrency testing.

## Exact safe production gate — unfulfilled
1. Identify actual Passenger/cPanel effective source and database without guessing paths or modifying runtime; independently identify legacy writer version, cron and responsibilities. Preserve all existing paid/pending walletless records and buyer delivery rights.
2. Read-only audit the complete legacy and new provider events and credits; detect reused TXIDs, orphan credits, malformed refs and inconsistent receipts before schema or live invoice changes.
3. Test migration graph against actual MariaDB + staged restore and verify `0042` is nonconflicting; no live DDL without a separately approved deployment and backup.
4. Either transition to an independently confirmed **exclusive writer** (with no remaining old-worker settlement) OR upgrade **all** active writers to a shared global canonical claim. Demonstrate that one old and one new worker racing on the *same TXID* yield exactly one credit and the loser rolls back, on the same MariaDB engine/isolation as production.
5. Execute the full Django, ORM, frontend, email/guest ownership, real product rights and byte-hash, refund/reversal, signed TRX proof and customer-file delivery suite on matching deployment source.
6. Complete a separately approved, minimally scoped commercial canary and reconcile real merchant-wallet receipt to ledger. No operator fee, trade, actual send, transfer, live activation or customer-data deletion without specific approval.

## Release and accounting truth
- **No main merge, cPanel/VPS deployment, real migration, live email, wallet transfer, payment, trade or expense was performed.**
- Current collected revenue, historical refunded totals, global company completeness and real production payment safety are **UNKNOWN**, not 0% or 100%.
- This file is an implementable hardening runbook, not proof of a live sale or authority to release.
