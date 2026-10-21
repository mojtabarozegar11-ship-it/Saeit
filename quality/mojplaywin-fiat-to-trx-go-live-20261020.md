# MojPlayWin — USD/fiat checkout, native TRX receipt: release gate (20 Oct 2026)

## Exact customer requirement
Customer uses an eligible card/fiat payment method on the provider's hosted checkout. Customer is **not required to register at MojPlayWin**. MojPlayWin receives a verified order, while merchant settlement is **native TRX on TRON mainnet**, not USDT-TRC20 and not a custodial balance reported as already received in the wallet.

Do not turn "USD price" into "card acceptance" without the payment processor's actual fiat-on-ramp activation. The provider's own fiat checkout may require phone confirmation, KYC or regional eligibility independent of MojPlayWin registration.

## Findings and live hold
- The existing two-book checkout pages (/store/product/72/checkout/ and /store/product/225/checkout/) return `login_required` for an anonymous visit on 20 Oct. These are **not guest fiat checkouts**.
- `mpw_fiat_to_trx_20261020/provider_adapter.py` can create an invoice only after verified merchant/payment/payout configuration. It is not a deployed, proven guest checkout, webhook/ledger or buyer-file entitlement implementation.
- Merchant account dashboard verification and live VPS/cPanel credentials **were not accessible** in this session; NEVER set a ready flag based only on this document, source code or a simulated test.
- Main Django Order.customer is required; do not attach anonymous buyers to an arbitrary account. Implement and independently review a private guest-order + signed recovery token workflow before accepting paid guest sales.
- Existing host has a shared Passenger/Django application serving protected child sites. A main-repo merge or Passenger restart is not a narrowly isolated deploy.
- No live money->NOWPayments->native TRX wallet->order ledger->private PDF canary was performed. Buyer funds must not be accepted until this has passed.

## Official merchant onboarding — must be performed inside owner's provider account
1. Use https://account.nowpayments.io/ and add a **TRON mainnet native TRX** receiving wallet in Payment Settings, not an arbitrary USDT token address. Keep API and IPN secrets only in private server environment.
2. Under Settings -> Fiat operations -> On-Ramp, request/activate the eligible fiat payment service, including any KYB identity/company documents actually requested by the provider. Check method and country availability and confirm final native-TRX merchant payout configuration inside the provider.
3. Confirm an invoice created via `POST https://api.nowpayments.io/v1/invoice` actually offers the customer's intended card/fiat method. The API's `price_currency=usd` field alone does not prove card acceptance; never assume `pay_currency` selects the merchant's settlement destination.
4. Configure the public IPN callback with NOWPayments HMAC SHA512 signature verification using `x-nowpayments-sig`. Test signature rejection, duplicate callbacks, incorrect price/order/invoice, non-TRX outcome, partial/refunded payment and late processing.
5. Verify invoice creation persists a unique order ID and invoice ID in durable, private storage before redirect. A customer receipt must be recoverable without a MojPlayWin password, through an expiring signed claim/receipt.
6. Verify payment using independently queried provider status and independently verified final native TRX transfer to the **configured merchant wallet**. The IPN's `finished` status alone is not proof of on-chain payout to this wallet; do not release files at this stage.
7. Perform a low-value real fiat test purchase: customer card -> provider accepted status -> native TRX received in merchant wallet -> exactly one paid ledger record -> authorized private download; verify cancellation, retry and refund behavior, support notices and customer access recovery.
8. Before publishing a live Buy button: restore a full off-host backup in isolation, confirm protected subsite invariants, and deploy the MojPlayWin root-only change atomically with scoped rollback.

## Code gates
`merchant_release_report` lists the disabled gates without exposing secrets.
`create_invoice` now requires the release report to be completely green **in addition to** basic API/IPN/merchant prerequisites. Do not flip these gates without externally verified evidence.

- MPW_FIAT_ONRAMP_APPROVED
- MPW_FIAT_TRX_PAYOUT_VERIFIED
- MPW_FIAT_IPN_PUBLIC_VERIFIED
- MPW_FIAT_PRIVATE_DELIVERY_VERIFIED
- MPW_FIAT_TENANT_ISOLATION_VERIFIED
- MPW_FIAT_BACKUP_RESTORE_VERIFIED
- MPW_FIAT_LIVE_CANARY_VERIFIED
- NOWPAYMENTS_API_KEY (secret; do not print)
- NOWPAYMENTS_IPN_SECRET (secret; do not print)

This file is a deployment hold, **not** a merchant activation receipt or proof of live checkout.

## Sources
- https://nowpayments.io/fiat-on-ramp
- https://nowpayments.io/help/payments/fiat-payments/how-to-accept-fiat
- https://nowpayments.zendesk.com/hc/en-us/articles/21345824322717-API-and-endpoint-description
- https://nowpayments.zendesk.com/hc/en-us/articles/21395546303389-IPN-and-how-to-setup
