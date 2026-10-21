# MojPlayWin payment gateway — 100/100 acceptance contract

**Owner decision, updated 2026-10-21:** Only the MojPlayWin **cryptocurrency payment gateway** (not other pages, content, factory, or business operations) can be accepted if independently verified as **100/100**. Customer bank cards, fiat-onramp and fiat-to-TRX conversion are **out of scope for now**. Native TRX on TRON and any other crypto rail actually offered by the live site (currently native ETH where enabled) must pass real tests. 99/100, passing CI alone, a styled page, a demo invoice, or a plausible chain transaction are NOT acceptance.

## Scope and gates (10 × 10 = 100)

Every gate is mandatory. No averaging, compensating points, or rounding. A partial pass is BLOCKED, not "nearly ready".

| Gate | Points | Required evidence in production |
| --- | ---: | --- |
| mobile_desktop_visuals | 10 | Real Chrome/Firefox/Safari (including Android/iOS), responsive branded checkout with no overflow/visual defects; human visual sign-off |
| accessibility_localization | 10 | WCAG 2.2 AA tests, keyboard/screen reader testing, readable status messages, currency/language display |
| transparent_amount_network_fees | 10 | Exact server-issued crypto quote (native TRX, native ETH if offered; USDT-TRC20 only when explicitly supported), receiver, network, minimum charge and expiry, with disclosed fees before payment |
| guest_purchase | 10 | Complete guest cryptocurrency purchase without forcing a MojPlayWin account or subscription, with strict order ownership and recipient proof |
| direct_trx_checkout | 10 | TRON-mainnet native TRX correctly routed to merchant-controlled wallet, unique invoice binding and independent finality validation |
| crypto_asset_network_coverage | 10 | All advertised crypto payment options (native TRX on TRON, native ETH if publicly offered) independently verified on their exact mainnets, recipient addresses and asset denominations; no phantom rails |
| invoice_and_wallet_security | 10 | Server-only secrets, CSRF, authz, no redirect/receipt spoofing, accurate recipient/amount, non-replayable order identifiers |
| finality_reconciliation | 10 | Exact sender/receiver/asset/amount checked by independent mainnet RPC/indexers; chain finality, duplicate tx, insufficient amount, wrong network/asset, expiry, replay and race handling |
| recovery_and_operations | 10 | Expiry, provider outages/timeouts, idempotent retries, safe refund/support path, recovery when customer closes/reloads, alerting and documented rollback |
| real_paid_delivery | 10 | Independent end-to-end **real** production purchase evidence: invoice → transfer → confirmed merchant receipt/settlement → customer-specific private download and recoverable receipt |

## Deferred, NOT part of current 100-point acceptance

Fiat/card, fiat-onramp merchant registration, conversion to TRX, KYB and fiat-provider API credentials are postponed until an explicit later owner instruction. Their absence must **not** block acceptance of a demonstrably safe cryptocurrency-only checkout. Do not enable these routes, describe them as active, or substitute a fiat checkout for a native-crypto invoice.

## Acceptance rules

- **No real, trusted evidence → NOT VERIFIED / BLOCKED.** Do not fabricate any score, real payment, revenue, or receipt.
- Evidence must be **external to test mocks**, come from the real production environment, pass independent review and be fresh. Keep confidential receipts, customer details, wallet secrets and transaction data in private storage, not in this repository.
- The optional signed private attestation checked by `scripts/mpw_payment_100_acceptance.py` confirms only the authorized verifier submitted a manifest. **The attestation is not a substitute** for independently examining all underlying evidence. A PASS may be reported externally only after that examination and explicit owner sign-off.
- Any critical security/financial problem overrides arithmetic: fail closed even when other checks pass.
- This acceptance gate is read-only. It does NOT activate processor accounts, enable live payments, change checkout code, process funds or deploy.
- Upgrading production checkout requires a separate, authorized deployment and post-release retest. Results expire on material payment-code/provider changes.
- If 100/100 is not proved, continue repairs and testing; do not label the gateway production-accepted.

## Current status, 2026-10-21

Two main checkout templates have had visual upgrades with successful GitHub Actions deployment checks. The current objective is **crypto-only**, not fiat/card onboarding. A complete real native TRX (and any other publicly advertised crypto rail) transaction followed by verified private product delivery has **not** been demonstrated. Therefore **100/100 is NOT established**. No current numeric gateway score is certified.
