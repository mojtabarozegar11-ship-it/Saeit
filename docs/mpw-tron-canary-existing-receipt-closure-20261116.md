# Owner TRON payment rollout — existing-payment and canary truth (2026-11-16)

This change was motivated by **actual authorized cPanel evidence**, not a source-only inference:
GitHub Actions [run 43760245836](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43760245836), job 132953216341, 2026-11-15 20:50 UTC, printed only sanitized payment settings.

## Evidence already established
- Existing live TRX beneficiary `_configured_receiver()` **exactly matches** the owner-approved Trust Wallet QR `THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73`.
- `MPW_COMMERCE_INVOICING_ENABLED`, `MPW_COMMERCE_REAL_RPC_ENABLED`, `MPW_COMMERCE_SETTLEMENT_ENABLED`, `MPW_COMMERCE_DOWNLOADS_ENABLED` and `MPW_WALLETLESS_TRX_PUBLIC_ENABLED` were all real Python `True`.
- `MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED` was explicitly Python `False`, while the called commercial-read-only gate returned `ok: true`.
- `MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED` was Python `True`. That environment state is **not** a settled-payment certificate or proof of a buyer's consent.
- The walletless private consumer-credit bridge `core/crown_tron_receipts.py` can validate stored finalized ledger evidence, but must not be confused with *fresh independent chain finality*.
- Buyer free-email double opt-in root previously observed HTTP404, so an email subscription cannot be treated as a paid customer.

## Added diagnostic for one real binary decision
The now self-contained `scripts/mpw_trx_canary_existing_receipts_readonly_20261116.py` produces:
- Whether live public and canary settings are inconsistent in the currently observed commercial gate.
- Whether the gate source directly mentions the canary and public flags (a **source mention**, not proof that helper code enforces them).
- Whether any already-persisted paid `mpw_walletless_trx_v1` intent exists; only first 25 paid records are checked with the independently coded stored-ledger receipt validator.
- Whether any generic delivery-success event was recorded **without** wrongly linking it to a paid order.
- Scope exhaustion and explicit non-evidence of a matched delivered customer, fresh independent chain validation or money amount received.

The report prints **no buyer names, email addresses, order IDs, exact totals, paid amounts, invoice IDs, TXIDs, other receiver addresses, keys, passwords, session secrets or cookies**.
The factory-runner workflow pins exact script Git blob SHA; cPanel is read-only, authenticated and host-key pinned. No new invoice, test payment, customer email or production change is performed.

## Release rule
Never set `MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED` to true merely to make checkout work. A real customer-owned, finalised native TRX payment must be independently reconciled to a server-issued unique invoice and linked to an actually delivered asset. Existing **real** ledger evidence may allow a fee-free verification; otherwise a legitimate buyer transaction, not fake income, is necessary. No expense, transaction fee, network broadcast, live trade or new customer obligation is authorized by this audit.

Payment first, verify independently, deliver the product, then reconcile accounting. Wallet ownership and the legal permission to receive are already owner-attested and are **not** the remaining technical blocker.
