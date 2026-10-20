# MojPlayWin — required checkout contract (2026-10-20)

## Merchant requirement (supersedes the staged wallet-to-wallet guest checkout)
A buyer must be able to pay in a **supported fiat currency** (for example USD or EUR) using an allowed local/card payment method, while the merchant receives **native TRX on TRON mainnet** to the merchant's existing verified wallet. The buyer must not be required to register for a MojPlayWin customer account or purchase a subscription. A fiat-onramp provider might independently require identity checks or phone verification.

A USD-priced listing is NOT proof that fiat card payments are accepted. A crypto wallet alone cannot process bank-card transactions or convert fiat. The staged `mpw_guest_trx_20261020/` code is strictly **not deployed**, is a different product (buyer sends TRX), and MUST NOT be enabled as a substitute for this requirement.

## Acceptance requirements
1. Operator chooses and onboards a regulated/approved fiat-onramp merchant, with KYB and jurisdiction/currency support verified.
2. Merchant account defines **TRX (native TRON)** as settlement currency and the pre-existing merchant payout wallet; validate network, ownership, permissions, quote limits, fees, and expected payout treatment with the provider.
3. Hosted checkout accepts only the provider's supported fiat currencies/methods; no promise of universal global currency acceptance or zero-KYC.
4. MojPlayWin creates one server-side priced guest order with a hard-to-guess receipt; redirects to the authorized provider-hosted checkout. Merchant API and webhook keys remain server-side.
5. A signed webhook **and independent provider status/settlement verification** must bind invoice ID, order ID, amount, currency, final payment state and TRX settlement to the intended merchant before any paid file is released. Handle duplicates/replays, partial/refunded payments and expiry safely. Test with provider-approved non-live fixtures before opening the live button.
6. Complete end-to-end tests must cover guest purchase, actual payment, settled TRX balance/wallet transfer, private download and independent sibling subsite isolation; without verified evidence, remain disabled.
7. Any BUY NOW button must stay disabled or truthfully state the payment isn't yet available until these conditions pass.

## Current verified blocker
The MojPlayWin production settings do not have an approved fiat-onramp provider or merchant API authorization configured. Only the native ETH/TRX wallet-to-wallet path and TRX receiver are presently confirmed. Creating an API key or a processor merchant account requires the human merchant's authorization; code cannot generate it.
