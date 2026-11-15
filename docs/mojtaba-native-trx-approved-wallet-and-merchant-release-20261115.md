# Owner-approved TRON receiving wallet — source and release record

Date: 2026-11-15. Merchant front end: `mojplaywin.com`. Sole service/educational-signals agent: `mojtaba.bot.ai`.

## Owner authorization and QR validation
- The owner supplied a **Trust Wallet TRON Receive** screenshot and expressly stated on 2026-11-15 that receiving TRON payments into the wallet is owned/legally authorized.
- The wallet address used by the source is the **decoded QR payload**, not visually transcribed page text. A misleading lookalike `Z` near the end is **not** the QR's `2`; the lookalike fails Base58Check.
- The approved QR's 34-character TRON Base58Check address has prefix-byte `0x41`, a matching double-SHA256 4-byte checksum, and is stored in `services/mojtaba_tron_owner_receiver.py`; **no** seed, private key or withdrawal permission is needed.
- This is a user attestation of control and permitted receipt. Address-format validation does not independently prove custody, account activation, seller jurisdiction, or actual income.

## Unambiguous merchant acceptance rules
1. Only `tron-mainnet` native `TRX` (6 decimals, quote integer `sun`) is presently in scope. A TRC20 token transfer, USDT transfer or another blockchain is not a native TRX invoice payment.
2. Only exactly `mojplaywin.com` is registered to merchant `mojplaywin-store`; do not infer `www`, `zomorodmelal.ir`, brand hostnames or `mojtaba.bot.ai`. New hosts require individually verified registry+contract+tenant checks.
3. Owner-provided receiver is pinned to the QR payload. A client cannot choose a different receiving wallet by URL, form, cookie, webhook or Host header.
4. Both `MPW_TRX_INVOICE_RELEASE_VERIFIED=true` and `MPW_TRX_SOLIDITY_RELEASE_VERIFIED=true` in the **server environment** are needed for the merchant binding to become active; both default `false`. They must be set only after independently confirming actual production billing, wallet control, controlled return/exception handling, chain finality, and backups. These flags are **not proof** by themselves.
5. Each customer must receive a server-issued, authenticated, expiring invoice with a **unique order ID and amount in sun**, and an accurate product-specific scope/refund contract. A static address/QR without such a record is only a payment destination, not a commercial checkout.
6. For each claimed TRX payment, independently query `/walletsolidity/gettransactionbyid`; validate an actual native `TransferContract`, exact recipient, value, sender as applicable, invoice time/expiry and that the TXID has not been used by another order. Record cryptographic transaction proof once. Broadcast or FullNode alone is not finality.
7. Underpayments, overpayments, duplicate TXIDs, late transactions, wrongful recipients and refunds remain explicit exception cases; do not silently grant services or recognize revenue.
8. Grant educational report/download access **only after** independently verified settlement; record actual deliverable and buyer receipt. No trading, broker funding, token launch or profit promise is implied.
9. Existing invoices for another recipient or domain must **not** be rewritten or reassigned to this newly approved receiving wallet; preserve immutable invoice snapshots.

## Current implementation and truthful state
- `services/mojtaba_tron_owner_receiver.py`: QR-verified checksum address, exact domain/merchant-native-network registry, dual release gates and immutable informational terms (no payable invoice data).
- `config/settings.py`: safely registered merchant details, both release flags default OFF. No actual deployment or environmental switch is performed by a source commit.
- `core/management/commands/moj_tron_receiver_status.py`: read-only operator shape/flags without logging buyer addresses, passwords, payment TXIDs or unverified income.
- Regression tests: QR typo, Base58Check, wrong host, false flag, receiver substitution, state safety and read-only status; no real payment, SMS/email or wallet signing.
- **Live billing status: UNVERIFIED/NOT ACTIVATED BY THIS CHANGE**. Existing guest TRX settlement code is partly referenced from paths not present in the Saeit main repository; merchant binding source existence does not establish a working production invoice → payment → settlement → delivery path. A separate integration audit and controlled release remain mandatory.
- Current free signals funnel and backend were also previously found to have live-path mismatches (subscription API HTTP 404), so don't market the solution as launched until host evidence is complete.

Reference: official TRON documentation, https://developers.tron.network/docs/confirmation-semantics (native direct transfer solidity confirmation).

**No new spending, customer funds, TRON transaction, email, trade, payment capture, source merge, or cPanel deployment was performed by creating this record.**
