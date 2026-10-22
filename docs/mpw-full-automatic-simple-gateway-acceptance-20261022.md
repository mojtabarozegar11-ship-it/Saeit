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


## 22 October — anonymous checkout and browser handoff

- The test-only Django guest module creates an individual password-disabled
  buyer behind the scenes with no form or mandatory login.
- The cookie is signed by Django and contains a 256-bit random claim.
  Only its SHA256 digest is held in isolated MariaDB; HttpOnly, Secure,
  SameSite=Lax and checkout-only path are enforced.
- Atomic per-IP HMAC-keyed hourly throttle permits five new identities.
- Guest checkout delegates to the same authenticated-order, immutable quote,
  actual Django ledger, owner-scoped paid-status and private-download logic.
- A 120-second, single-use high-entropy wallet browser transfer ticket
  allows the TronLink DApp browser to obtain its OWN signed checkout cookie.
  This avoids exposing the 30-day original guest claim via a deep link.
- Ticket replay, forged claim, expiry, owner mismatch and missing receipt
  all fail closed; the original browser token remains valid.
- 15 real Django/MariaDB isolated tests passed on Actions run 39728316387:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39728316387
- The suite includes simulated chain confirmation, real Django ledger
  entries and the owner-only private-file download endpoint.

## Remaining production blocks

No real mainnet TRX transfer has been successfully dual-verified against
two independently controlled authenticated TRON SolidityNode providers.
No safe staging deployment with reversible migrations/restore and
real money-to-file download has been proven. Guest routes remain UNMOUNTED
and all code is guarded to run against a test_ MariaDB schema only.

Before public use, scrub 120-second handoff tokens from webserver access
logs, enforce edge rate limiting, verify the signed HTTPS wallet deep-link
and complete a consented tiny mainnet payment in private staging.
No production writes were made by these workflows.
