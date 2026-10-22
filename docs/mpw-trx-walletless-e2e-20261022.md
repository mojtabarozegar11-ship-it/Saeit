# MojPlayWin — walletless TRX automatic checkout, 22 October 2026

## Scope and progress
This branch builds the isolated full-cycle software kernel for:
- Signed-in buyer order ID and immutable USD total
- 10-minute TRX invoice using fresh USD/TRX price
- Permanently unique SUN amount with MariaDB InnoDB lock and idempotent reservation
- Responsive mobile invoice, address-only QR and exact amount copy
- Polling server-side payment status; zero client-side authorizations
- Bounded unattended scan of candidate TRX transfers
- TWO independently authenticated solidified TRON proofs (injected in tests)
- Atomic test receipt, ledger, and customer-scoped entitlement in separate disposable MariaDB
- Fail-closed duplicate/underpay/overpay/expiry/provider-disagreement tests

## Execution evidence
- Existing core kernel: 16 tests (GitHub Actions 39712606580)
- Separate MariaDB reservation: 6 tests (39713211967)
- Atomic receipt/ledger/grant: 9 tests (39715408314)
- QR and mobile status/presentation: 4 tests (39716031447)
- Automatic scan and two-provider proof simulation: 6 tests (39716234530)

These are independent synthetic functional tests. No real-chain paid transaction,
no live-customer sale, and no live merchant-file delivery has been verified.

## Critical release blockers
1. The app has NOT been installed into the active Passenger URL routing.
2. There is NO Django production adapter for real Order, OrderItem,
   CommerceReceipt, LedgerEntry and CommerceFulfillment. The standalone
   MariaDB tables are **test shadow tables only**, NEVER commercial financial books.
3. Need provision two actual separately controlled trusted TRON
   SolidityNode sources and verify both transaction body + execution receipt.
   Different source_id strings alone are NOT proof of independence.
4. Need integrate the native existing TRX/ETH CommerceInvoice unique amount
   constraint into the SAME transactional allocation, or disable legacy TRX
   issuance during walletless rollout. Checking a live table outside a shared
   lock does not prevent the cross-engine race.
5. Must install and verify the pinned pure Python QR dependency (segno),
   then bind it to a Django route with CSRF, user identity, rate limiting,
   paid owner-scoped download and a secure no-cache Content Security Policy.
6. Authoritative TRX recipient should be checked via Base58Check checksum
   and match the actual configured mainnet receiving wallet.
7. Run a **tiny, consented real mainnet transaction** with amount matching,
   independent solidification, exact accounting, paid-only file download and
   emergency disable/restore against the real staging installation.
8. Recover a tested encrypted staging backup and validate deployment rollback
   before releasing any customer-facing payment instructions.

## Do not enable
Do NOT set an enabling flag, publish payment QR/recipient to customers,
create merchant financial records, change the active cPanel DB or
redirect live checkout paths based on these simulated tests.
The existing MojPlayWin live checkout remains the last confirmed deployed mode.
No workflow in this branch mutates the live system.

## Source contracts
- services/mpw_trx_walletless_core.py: exact quote and dual-source verification
- services/mpw_trx_walletless_reservation.py: isolated MariaDB reservation
- services/mpw_trx_walletless_finalize.py: test-only atomic receipt/ledger/grant
- services/mpw_trx_walletless_reconcile.py: bounded automatic matching simulation
- services/mpw_trx_walletless_checkout_ui.py: CSP-bound QR and polling presentation
- services/sql/mpw_walletless_trx_isolated_v1.sql: isolated test schema, not migration

## Policy
No private key, recovery phrase, card secret, money transfer, paid entitlement,
or production DNS/site mutation may be introduced by a test-only workflow.
A live launch requires independent real evidence, not a green CI badge.


## 22 Oct addendum — Django MariaDB integration progress

- Live read-only Django/Passenger and MariaDB model audit: GitHub Actions 39716945449 (success).
- New Django Order, LedgerEntry, CommerceFulfillment test-only bridge, guarded against production database writes.
- Five genuine Django ORM + disposable MariaDB financial tests passed: Actions 39717903431.
- Six production write-guard and owner-only download checks passed: Actions 39717522544.
- Existing TRON solidity-RPC implementation found on cPanel; two independently governed RPC sources have NOT been established: Actions 39718128732.

### Public launch remains OFF

The above is a staging/test code achievement only; it is not actual paid TRX delivery.
The new code is not installed in public Passenger routes and no live QR has been issued.
Do NOT fill legacy sender-signature fields with forged values or disable the test_ database safety gate.

### Still required before public mainnet

1. Configure, externally verify and independently pin two real TRON finality providers.
2. Bridge unique invoice allocation and tx replay protection with the legacy real CommerceInvoice writer without races.
3. Run walletless buyer authentication, protected order and invoice endpoints and owner-scoped download in actual staging.
4. Validate atomic ledger and fulfillment against the real site's backed-up isolated staging MariaDB.
5. Restore from a verified backup and perform a small owner-approved real transaction before live enablement.
