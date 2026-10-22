# MojPlayWin: acceptance contract for EASY FULLY AUTOMATIC payment

## Customer journey — release gate

The interface must take a buyer from product choice to a valid file download
with minimal manual steps:

1. Choose product and tap **Pay**. Create/reuse an idempotent order/invoice.
2. On mobile TronLink DApp, fill exact recipient and amount by one tap;
   the customer ONLY approves the TRX transfer in their own wallet.
   No site-side private keys, seed words, or mandatory wallet-message signing.
3. If another wallet is used, show copyable address, exact amount and QR
   that clearly states when it encodes only an address. Never imply
   a QR includes the amount unless it really does.
4. No manual sender entry, tx hash entry or "I paid" button.
   Scan on-chain transactions automatically, with multiple bounded retries.
5. Only when independent genuine finality evidence and actual ledger
   records agree, move paid -> buyer-only secure digital delivery.
6. No overpayment, late-payment or ambiguous-payment auto grants:
   preserve evidence and surface support/review, not false success.
7. Mobile-friendly responsive layout and accessible live status.
   No silent double payment; stale invoices must never invite transfer.
8. Buyer-less guest checkout is the desired least-friction mode,
   but MUST first have a cryptographically authenticated receipt/claim
   plus account and duplicate prevention in the SAME MariaDB ledger.
   The currently tested web pilot requires login; do NOT describe
   it as guest-enabled.

## What is actually implemented and tested in PR #832

- Real Django ORM test database order/financial/fulfillment bridge.
- No-signature TRX invoice reservation and immutable exact SUN amount.
- Responsive QR and exact amount copy plus new TronLink injected one-tap
  wallet-transfer request with explicit user confirmation.
- Owner-scoped payment status and physical private-file download guard.
- Per-buyer idempotent POST endpoint and example staging URL patterns,
  not mounted to active production routes.
- Duplicate/underpayment/provider-disagreement/replay rejection.
- 12 integrated Django+MariaDB tests green:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39723430635
- Two isolated buyer UI / JavaScript tests green:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39722391062
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39722391174

## Do not claim commercial readiness yet

- No real signed-in buyer money was sent or received in this test.
- Two independent TRON provider credentials / live canonical transfer
  body+receipt verification remain unproven at cPanel staging.
- New database tables must be safely migrated with tested backup rollback.
- Guest checkout is not implemented in the new MariaDB financial path.
- Staging URL patterns require isolated staging host + test database and
  are deliberately NOT mounted in the active MojPlayWin application.
- HTTP endpoints and no-buyer account support cannot be called live
  until actual full-chain proof, real data backup, security review,
  and permitted small real payment pass.
- Existing legacy live gateway remains unchanged.

**Production activation is FAIL-CLOSED until the entire test suite,
provider attestation, signed-staging small payment and private
download tests all pass.**

This contract takes precedence over one-off UI changes, reports,
or unverified "100/100" readiness declarations.
