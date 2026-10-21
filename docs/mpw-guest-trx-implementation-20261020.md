# MojPlayWin — crypto-only payment scope update, 2026-10-21

**Owner's latest instruction supersedes the 2026-10-20 fiat/card requirement below.** For now, MojPlayWin accepts **cryptocurrency payment only**, centered on native TRX on TRON mainnet and any other actually enabled/proven crypto rail (such as native ETH). Fiat/card acceptance, Banxa onboarding, merchant KYB for on-ramp, bank payments and fiat-to-TRX conversion are expressly **deferred**, not prerequisites for crypto-only acceptance.

The requirement to distinguish cryptocurrency transfer from USD *price display* still applies. USD-denominated product listings do not imply that credit-card payments are supported. All publicly offered crypto rails must have real mainnet payment evidence before the payment gateway can receive **100/100** approval. Current 10×10 quality gates live in [mpw-payment-gateway-100-acceptance-20261021.md](mpw-payment-gateway-100-acceptance-20261021.md).

The staged `mpw_guest_trx_20261020/` path is **disabled**, not a proven live guest-payment mechanism. It may be evaluated for native-TRX payments only after wallet-ownership, unique invoice amount, quote expiry, secure buyer claim, independent TRON Solidity finality, replay protection, and paid digital file release receive end-to-end tests. **Do not enable it blindly or declare a paid order without mainnet proof.**

The staged `mpw_fiat_to_trx_20261020/` provider/guest prototype is retained as reference only; its presence is neither an active fiat payment route nor a blocker for crypto-only acceptance. Never swap a currently functioning native crypto path for an unapproved fiat provider.

---

## Historical contract (2026-10-20), superseded and not active

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
