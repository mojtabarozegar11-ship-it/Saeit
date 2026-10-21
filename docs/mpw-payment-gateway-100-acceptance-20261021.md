# MojPlayWin payment gateway — 100/100 acceptance contract

**Owner decision, 2026-10-21:** Only the MojPlayWin **payment gateway** (not other pages, content, factory, or business operations) can be accepted if independently verified as **100/100**. 99/100, passing CI alone, a styled page, a demo invoice, or a plausible chain transaction are NOT acceptance.

## Scope and gates (10 × 10 = 100)

Every gate is mandatory. No averaging, compensating points, or rounding. A partial pass is BLOCKED, not "nearly ready".

| Gate | Points | Required evidence in production |
| --- | ---: | --- |
| mobile_desktop_visuals | 10 | Real Chrome/Firefox/Safari (including Android/iOS), responsive branded checkout with no overflow/visual defects; human visual sign-off |
| accessibility_localization | 10 | WCAG 2.2 AA tests, keyboard/screen reader testing, readable status messages, currency/language display |
| transparent_amount_network_fees | 10 | Server-issued exact quote, explicit native TRX versus USDT-TRC20, correct network, minimum charge and expiry, final fees shown before payment |
| guest_purchase | 10 | Full genuine guest buyer flow without MojPlayWin account or subscription, preserving lawful processor identity checks |
| direct_trx_checkout | 10 | TRON-mainnet native TRX correctly routed to merchant-controlled wallet, unique invoice binding and independent finality validation |
| fiat_to_native_trx | 10 | Provider-approved fiat/card method in verified supported jurisdiction and genuine native TRX merchant settlement, no invented provider/currency support |
| invoice_and_wallet_security | 10 | Server-only secrets, CSRF, authz, no redirect/receipt spoofing, accurate recipient/amount, non-replayable order identifiers |
| finality_reconciliation | 10 | Exact sender/receiver/asset/amount checked on chain/provider; finality, duplicate tx/webhook, short payment, wrong network, partial/refund, race handling |
| recovery_and_operations | 10 | Expiry, provider outages/timeouts, idempotent retries, safe refund/support path, recovery when customer closes/reloads, alerting and documented rollback |
| real_paid_delivery | 10 | Independent end-to-end **real** production purchase evidence: invoice → transfer → confirmed merchant receipt/settlement → customer-specific private download and recoverable receipt |

## Acceptance rules

- **No real, trusted evidence → NOT VERIFIED / BLOCKED.** Do not fabricate any score, real payment, revenue, or receipt.
- Evidence must be **external to test mocks**, come from the real production environment, pass independent review and be fresh. Keep confidential receipts, customer details, wallet secrets and transaction data in private storage, not in this repository.
- The optional signed private attestation checked by `scripts/mpw_payment_100_acceptance.py` confirms only the authorized verifier submitted a manifest. **The attestation is not a substitute** for independently examining all underlying evidence. A PASS may be reported externally only after that examination and explicit owner sign-off.
- Any critical security/financial problem overrides arithmetic: fail closed even when other checks pass.
- This acceptance gate is read-only. It does NOT activate processor accounts, enable live payments, change checkout code, process funds or deploy.
- Upgrading production checkout requires a separate, authorized deployment and post-release retest. Results expire on material payment-code/provider changes.
- If 100/100 is not proved, continue repairs and testing; do not label the gateway production-accepted.

## Current status, 2026-10-21

Two main checkout templates have had visual upgrades with successful GitHub Actions deployment checks. A complete real paid fiat/native TRX transaction followed by verified private product delivery has **not** been demonstrated. Fiat processor merchant approval and payout have not been verified. Therefore **100/100 is NOT established**. No current numeric gateway score is certified.
