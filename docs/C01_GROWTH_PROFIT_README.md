# C-01 | Private two-market cash-funnel evidence reconciliation (v1)

Run: python3 scripts/c01_growth_profit_report.py --input /private/path/events.csv --as-of 2026-11-01 > /private/path/summary.json

CSV header (exact order):
event_id,occurred_at,market,unit_id,channel,campaign_id,event_type,order_id,currency,amount,quantity,evidence_ref

Markets: ZM_IR and MPW_GLOBAL. Event types: visit, lead, paid_order, refund, cogs, ad_spend, other_cost. Currency is recorded, **never converted**. All financial rows require a non-empty non-personal evidence reference. Paid orders and refunds require positive amounts; COGS and expenses may be zero with evidence. All financial rows have quantity 1. Visit/lead events use amount 0, no order ID and positive quantity. Timestamps must include ISO-8601 timezone offsets. The cutoff is YYYY-MM-DD.

Order-linked events (paid_order, refund, cogs) must share market/unit/channel/campaign/currency and an order ID; exactly one paid order and at most one COGS event per order. Refund totals cannot exceed the paid order. A group requires explicit COGS per order, ad spend and other cost evidence (including explicit zero where applicable) before cash contribution is shown.

The output includes only aggregated counts/sums, the source CSV SHA-256, and the reporting period. It does not include raw order IDs, receipt IDs, names, phone numbers or email addresses. Never commit real transactions or reports to the public repository. Keep input/output files in access-controlled private paths.

**Interpretation:** all amounts are supplied records, **not independently bank-confirmed facts**. Net receipts are paid orders less recorded refunds. Gross margin and contribution are null if cost evidence is incomplete, not zero. ROAS is net receipts divided by recorded ad spend; zero ad spend yields null. Cost per paid order is **not** CAC. CAC and LTV remain null without customer cohorts. Channel tags are descriptive, not causal attribution. Do not use this report to justify ad spend or claim live sales without payment and delivery reconciliation.

Tests: python3 -m unittest discover -s tests -p 'test_c01_growth_profit_report.py' -v (stdlib only; synthetic evidence).

No deployment, DB migration, external message, advertising spend, order, payment, or VPS factory operation.
