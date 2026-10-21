# MojPlayWin — merchant payment activation blockers (2026-10-21)

Scope: MojPlayWin payment gateway ONLY. This file is an actionable evidence checklist and MUST NOT be considered activation, payment testing or a 100/100 pass.

## What is already proven
- Production checkout routes for verified books 72 and 225 dispatch to `mpw_commerce.product_checkout_page`; authenticated dry gate passed.
- The live Django application has true flags for `MPW_COMMERCE_RELEASE_READY`, customer HTTP, invoicing, settlement, native RPC, auto reconciliation and protected downloads. This is **NOT** proof of a real payment.
- The signed-IPN and independent processor-payment reconciliation adapter exists in GitHub, but is **not installed as a live card processor**.
- Existing fiat on-ramp API credentials, approved card merchant acceptance and native TRX payout proof were not seen by the read-only production probe. That probe inspected runtime environment variables, so its results are not an exhaustive inventory of all secret stores.

## External acceptance — cannot be done in code
1. Merchant logs into https://account.nowpayments.io/ and completes profile and permitted-country merchant onboarding with real verified legal identity. Do not place identity documents or OTPs in code/chat.
2. Settings → Payments → Payout wallets: register and verify the **existing merchant-controlled native TRX address on TRON mainnet**; explicitly distinguish TRX from USDT-TRC20. Enable account 2FA, verified wallet/address and IP controls.
3. Settings → Payments → API keys: create a restricted API key and IPN signing secret; install only in secret manager on the approved payment server. Never commit, paste or print raw keys.
4. Settings → Fiat operations → On-Ramp: select supported provider and complete its own KYB. Obtain written proof of supported buyer countries, payment methods (card/Apple Pay/Google Pay), supported invoice currencies, account limits, chargeback/refund treatment and fiat-to-**native-TRX** payout. Approval and actual wallet settlement must be independently verified.
5. Confirm whether fiat payments settle into custody or directly to native TRX wallet; if custody, document independent paid-entitlement policy and wallet withdrawal evidence separately. A payment processor's `finished` flag is insufficient as evidence of final wallet delivery.
6. Obtain the provider's current fiat/card **minimum** (not the crypto-to-crypto TRX minimum). The USD 0.03 test product must remain restricted to an eligible direct-TRX test flow, or fail closed for any provider that forbids micro-transactions. Never synthesize a lower limit.

## Technical tasks that remain unproven
- Independently verify **both** crypto-mainnet paid-to-private-download and a genuine fiat/card-to-native-TRX purchase, with exactly matching order, fiat price, network, receiver, processor identifiers, paid status and ledger evidence.
- Treat `finished` as non-final for entitlement if `actually_paid < pay_amount`; NOWPayments merchant settings may mark an underpaid payment `finished`. Verify actual amount and signed IPN against an independent status lookup.
- Test mobile browser login (cookie-preserving and cookie-less), no-account guest flow, interrupted checkout, timeout, refund/chargeback, short/wrong asset, webhook retry, replay and recovery of private digital product.
- Only a trusted independent assessment with **all 10/10 mandatory gates** can change payment acceptance to 100/100; until then hold commercial acceptance blocked.

## Official provider setup / evidence
- https://nowpayments.io/fiat-on-ramp
- https://nowpayments.zendesk.com/hc/en-us/articles/21341613323421-NOWPayments-Integration-Guide
- https://nowpayments.zendesk.com/hc/en-us/articles/18395434917149-Payment-statuses
- https://nowpayments.zendesk.com/hc/en-us/articles/27407237685917-Minimum-payment-amount

No key, PII, payout address, charge, sign-in or site-side payment toggle is modified by this document.
