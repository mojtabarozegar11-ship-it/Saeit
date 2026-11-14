# C21 — exact merchant-brand binding on already signed history

**Reconciled against the advancing PR #2310 parent at exact SHA `32c749ce8ac78e64b9cadd61945599826726f3a1`.** The parent ALREADY includes brand in the v1 HMAC canonical signal payload, tests rejecting cross-brand replay, and bounded price formatting to prevent huge Decimal exponents. C21 deliberately **preserves all those fixes** and does **not** rename its signature format, modify the underlying signed payload, discard recent parent tests or demand needless v2 re-signing.

## New, distinct commercial-review security boundary

A source-authenticated `SignalAudit` can still be supplied to `subscription_preflight` for a different merchant brand unless this final review explicitly verifies the scope. The C21 change requires `merchant_brand` from the **trusted protected tenant registration**, checks `merchant_brand == history.brand` with exact registered 17-brand identity, and returns a separate `merchant_scope_matches_history` failure instead of qualifying a different storefront. Missing/invalid brands fail closed. The same-brand case **only allows owner review**; checkout, public signals, subscription delivery, trades, customer receipts and paid entitlements remain disabled.

## Sibling integration and next gate
- The parent already protects brand-bound signal history; this PR is ONLY the missing merchant-to-history review link, avoiding duplicate source implementations.
- Separate [PR #2315](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2315) stores signed `SignalSourceEvent` with a **different** source envelope and durable uniqueness. Do not combine HMAC formats or trust a source key across tenants until a reviewed adapter maps a signed record to the exact protected merchant scope, and reconciles immutable source/version/DB records.
- [PR #2316](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2316) verifies site host/brand routes but does not prove any customer bought a subscription. The 17 brand routes are not 17 independently verified owned public hosts or licensed businesses.
- Independent trading history including losing trades, spread, slip/fees, time, legal license, customer permissions, refund/cancellation, TRX finality and proven subscription delivery are still required.
- No live website deployment, broker trade, customer email, marketing post, checkout or wallet action. Single bot `mojtaba.bot.ai`.
- Absolutely no posting/scheduling on owner profile `Dr.mojtaba.rozegar` including connected Metricool 7317306 and Facebook Page 102203064721826.

**Engineering constraint:** preserve latest parent's price-bounding, brand signatures, and strong tests. Draft stacked on parent. A green unit test is not independent performance or cash.
